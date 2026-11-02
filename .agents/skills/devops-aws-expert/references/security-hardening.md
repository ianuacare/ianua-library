# Security Hardening

Reference for `devops-aws-expert` skill — cloud security best practices.

---

## IAM Policy Design

### Least-Privilege Principles

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::myapp-uploads/*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-1"
        }
      }
    }
  ]
}
```

**Rules:**
- Never use `"Action": "*"` or `"Resource": "*"`
- Specify exact actions needed for the service to function
- Use resource ARNs, not wildcards
- Add `Condition` blocks to restrict by region, source IP, or tags
- Use `aws:PrincipalTag` for attribute-based access control (ABAC)

### Service Roles

- Every ECS task, Lambda function, and EC2 instance gets its own IAM role
- Use task roles (not instance roles) for ECS
- Separate roles for build vs deploy in CI/CD
- Review roles quarterly — remove unused permissions

### IAM Boundaries

```hcl
resource "aws_iam_role" "app" {
  name                 = "myapp-api-role"
  permissions_boundary = aws_iam_policy.boundary.arn
  assume_role_policy   = data.aws_iam_policy_document.ecs_assume.json
}
```

Use permissions boundaries to limit the maximum permissions any role can have.

---

## Security Groups and NACLs

### Security Group Design

```hcl
# ALB security group — only accepts HTTPS from internet
resource "aws_security_group" "alb" {
  name_prefix = "${local.name_prefix}-alb-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port       = 0
    to_port         = 0
    protocol        = "-1"
    security_groups = [aws_security_group.app.id]
  }
}

# App security group — only accepts from ALB
resource "aws_security_group" "app" {
  name_prefix = "${local.name_prefix}-app-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 3000
    to_port         = 3000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
}

# Database security group — only accepts from app
resource "aws_security_group" "db" {
  name_prefix = "${local.name_prefix}-db-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
}
```

**Rules:**
- Chain security groups: Internet → ALB → App → DB
- Reference security group IDs, not CIDR blocks, for internal traffic
- No `0.0.0.0/0` ingress except on ALB port 443
- Use `name_prefix` with lifecycle `create_before_destroy` for zero-downtime updates

### NACLs

Use NACLs as a second layer of defense (stateless firewall at subnet level):
- Block known malicious IP ranges
- Restrict outbound to necessary ports only
- Allow ephemeral ports (1024-65535) for return traffic

---

## WAF Configuration

```hcl
resource "aws_wafv2_web_acl" "main" {
  name  = "${local.name_prefix}-waf"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  # AWS Managed Rules — Core Rule Set
  rule {
    name     = "aws-managed-common"
    priority = 1
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesCommonRuleSet"
      }
    }
    visibility_config {
      sampled_requests_enabled   = true
      cloudwatch_metrics_enabled = true
      metric_name                = "aws-common-rules"
    }
  }

  # Rate limiting
  rule {
    name     = "rate-limit"
    priority = 2
    action { block {} }
    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      sampled_requests_enabled   = true
      cloudwatch_metrics_enabled = true
      metric_name                = "rate-limit"
    }
  }
}
```

**Recommended managed rule groups:**
- `AWSManagedRulesCommonRuleSet` — OWASP top 10
- `AWSManagedRulesKnownBadInputsRuleSet` — Log4j, etc.
- `AWSManagedRulesSQLiRuleSet` — SQL injection
- `AWSManagedRulesLinuxRuleSet` — Linux-specific attacks (if applicable)

---

## Encryption

### At Rest

| Service | Encryption method |
|---|---|
| S3 | SSE-S3 (default) or SSE-KMS for compliance |
| RDS | KMS encryption (enable at creation) |
| EBS | KMS encryption (default encryption per region) |
| DynamoDB | AWS owned key (default) or CMK |
| EFS | KMS encryption |
| SQS | SSE-KMS or SSE-SQS |
| SNS | SSE-KMS |
| Secrets Manager | KMS (default) |

### In Transit

- ALB: terminate TLS with ACM certificate
- Internal services: use TLS between all components
- RDS: enforce `require_ssl` parameter
- ElastiCache: enable in-transit encryption
- S3: use bucket policy to deny non-HTTPS requests

```hcl
# S3 bucket policy — deny non-HTTPS
resource "aws_s3_bucket_policy" "enforce_tls" {
  bucket = aws_s3_bucket.main.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyNonHTTPS"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = ["${aws_s3_bucket.main.arn}/*"]
      Condition = {
        Bool = { "aws:SecureTransport" = "false" }
      }
    }]
  })
}
```

### KMS Key Management

- Use separate KMS keys per service/purpose
- Enable automatic key rotation
- Define key policies with specific principals
- Use aliases for human-readable references

---

## ACM Certificate Management

```hcl
resource "aws_acm_certificate" "main" {
  domain_name               = "example.com"
  subject_alternative_names = ["*.example.com"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => dvo
  }
  zone_id = data.aws_route53_zone.main.zone_id
  name    = each.value.resource_record_name
  type    = each.value.resource_record_type
  records = [each.value.resource_record_value]
  ttl     = 60
}
```

- Use DNS validation (auto-renewing)
- Create certificates in `us-east-1` for CloudFront
- Use wildcard certificates (`*.example.com`) to cover subdomains

---

## Secrets Manager

```hcl
resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "${local.name_prefix}/db-credentials"
  recovery_window_in_days = 7
  kms_key_id              = aws_kms_key.secrets.arn
}

# Enable automatic rotation for RDS credentials
resource "aws_secretsmanager_secret_rotation" "db" {
  secret_id           = aws_secretsmanager_secret.db_credentials.id
  rotation_lambda_arn = aws_lambda_function.rotate_secret.arn

  rotation_rules {
    automatically_after_days = 30
  }
}
```

**Rules:**
- Rotate secrets automatically (30-90 day cycle)
- Use Secrets Manager for database credentials, API keys, third-party tokens
- Use Parameter Store (SecureString) for configuration values
- Never log secret values — log only the secret name/ARN

---

## AWS Security Services

| Service | Purpose | Enable for |
|---|---|---|
| **AWS Config** | Resource compliance monitoring | All accounts |
| **SecurityHub** | Centralized security findings | All accounts |
| **GuardDuty** | Threat detection | All accounts |
| **CloudTrail** | API audit logging | All accounts |
| **Inspector** | Vulnerability scanning | EC2, ECR, Lambda |
| **Macie** | S3 data classification | If storing PII |

**Minimum setup for any production account:**
1. CloudTrail enabled (all regions, S3 storage)
2. GuardDuty enabled
3. Config enabled with rules for encryption, public access, tagging
4. SecurityHub enabled aggregating findings
