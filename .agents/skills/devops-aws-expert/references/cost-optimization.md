# Cost Optimization

Reference for `devops-aws-expert` skill — AWS cost management and reduction strategies.

---

## Compute Cost Optimization

### Reserved Instances and Savings Plans

| Option | Discount | Commitment | Flexibility |
|---|---|---|---|
| On-Demand | 0% | None | Full |
| Savings Plans (Compute) | ~30-40% | 1 or 3 years | Any instance family, region, OS |
| Savings Plans (EC2 Instance) | ~40-50% | 1 or 3 years | Specific instance family + region |
| Reserved Instances | ~40-60% | 1 or 3 years | Specific instance type |
| Spot Instances | ~60-90% | None | Can be interrupted |

**Decision tree:**
1. Stable, predictable workloads → Savings Plans or Reserved Instances
2. Flexible, fault-tolerant workloads → Spot Instances
3. Short-term or unpredictable → On-Demand
4. Start with Compute Savings Plans (most flexible commitment)

### Spot Instance Strategies

**Good for:**
- CI/CD build runners
- Batch processing workers
- Dev/staging environments
- Stateless ECS tasks with proper retry logic

**Not suitable for:**
- Production API servers (unless mixed with on-demand)
- Stateful workloads
- Single-instance databases

**ECS Capacity Providers:**
```hcl
resource "aws_ecs_capacity_provider" "spot" {
  name = "${local.name_prefix}-spot"

  auto_scaling_group_provider {
    auto_scaling_group_arn         = aws_autoscaling_group.spot.arn
    managed_termination_protection = "ENABLED"

    managed_scaling {
      status          = "ENABLED"
      target_capacity = 100
    }
  }
}
```

### Right-Sizing

- Review CPU/memory utilization weekly for the first month, monthly after
- Target 60-70% average utilization for compute resources
- Use AWS Compute Optimizer recommendations
- Downsize over-provisioned instances (common: t3.large → t3.medium)
- For ECS: set task CPU/memory based on actual usage, not guesses

---

## Storage Cost Optimization

### S3 Storage Classes

| Class | Use case | Cost (per GB/month) |
|---|---|---|
| Standard | Frequently accessed | ~$0.023 |
| Standard-IA | Infrequent access (> 30 days) | ~$0.0125 |
| One Zone-IA | Non-critical, infrequent | ~$0.01 |
| Glacier Instant Retrieval | Archive, millisecond access | ~$0.004 |
| Glacier Flexible Retrieval | Archive, minutes-hours access | ~$0.0036 |
| Glacier Deep Archive | Long-term archive, 12-hour access | ~$0.00099 |

### Lifecycle Policies

```hcl
resource "aws_s3_bucket_lifecycle_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    id     = "transition-and-expire"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }

    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }

    expiration {
      days = 2555  # 7 years
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}
```

### EBS Optimization

- Delete unattached EBS volumes (check monthly)
- Use gp3 instead of gp2 (20% cheaper, better performance)
- Snapshot old volumes and delete the volume if not actively used
- Right-size volumes based on actual usage

---

## Data Transfer Cost Reduction

Data transfer is often the most surprising cost on AWS bills.

### Common Expensive Patterns

| Pattern | Cost | Alternative |
|---|---|---|
| NAT Gateway data processing | $0.045/GB | VPC endpoints for AWS services |
| Cross-AZ traffic | $0.01/GB | Keep related services in same AZ where possible |
| CloudFront to origin | $0.00/GB (free) | Use CloudFront to reduce origin load |
| Internet egress | $0.09/GB | Cache at edge, compress responses |

### Cost Reduction Strategies

1. **VPC Endpoints**: free for S3/DynamoDB (Gateway), reduce NAT costs for others
2. **CloudFront**: data transfer from CloudFront is cheaper than from ALB/EC2 directly
3. **Compression**: enable gzip/brotli at ALB and CloudFront (reduce bytes transferred)
4. **S3 Transfer Acceleration**: only for large uploads from distant locations
5. **PrivateLink**: for service-to-service within AWS (avoids NAT)

---

## Tagging for Cost Allocation

### Required Tags

```hcl
locals {
  default_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    CostCenter  = var.cost_center
    Team        = var.team_name
  }
}
```

### Cost Allocation Tags

1. Enable cost allocation tags in AWS Billing console
2. Use tags to create cost breakdowns by project, environment, team
3. Create monthly reports filtered by tag
4. Identify untagged resources and enforce tagging via AWS Config rules

```hcl
# AWS Config rule to enforce tagging
resource "aws_config_config_rule" "required_tags" {
  name = "required-tags"

  source {
    owner             = "AWS"
    source_identifier = "REQUIRED_TAGS"
  }

  input_parameters = jsonencode({
    tag1Key = "Project"
    tag2Key = "Environment"
    tag3Key = "CostCenter"
  })
}
```

---

## AWS Budgets

```hcl
resource "aws_budgets_budget" "monthly" {
  name         = "${var.project_name}-monthly-budget"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_limit
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "TagKeyValue"
    values = ["user:Project$${var.project_name}"]
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 50
    threshold_type            = "PERCENTAGE"
    notification_type         = "FORECASTED"
    subscriber_email_addresses = var.budget_alert_emails
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = var.budget_alert_emails
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = var.budget_alert_emails
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }
}
```

**Alert thresholds:**
- **50% forecasted**: early warning, review spending trends
- **80% actual**: investigate, identify cost drivers
- **100% actual**: immediate action, notify stakeholders

---

## Monthly Cost Review Checklist

- [ ] Review AWS Cost Explorer — compare to previous month
- [ ] Check for unused resources: unattached EBS, idle load balancers, unused Elastic IPs
- [ ] Review NAT Gateway data processing costs
- [ ] Check for right-sizing recommendations (Compute Optimizer)
- [ ] Review Reserved Instance / Savings Plan utilization
- [ ] Verify S3 lifecycle policies are working (check storage class distribution)
- [ ] Check for untagged resources
- [ ] Review data transfer costs by service
- [ ] Update budget forecasts if spending patterns changed
- [ ] Document any cost anomalies and root causes

---

## Quick Wins

| Action | Typical savings |
|---|---|
| Delete unused EBS volumes | $10-100/month |
| Release unused Elastic IPs | $3.65/month each |
| Stop idle dev/staging instances off-hours | 60% on those instances |
| Switch gp2 → gp3 EBS volumes | 20% on EBS costs |
| Add S3 lifecycle policies | 50-90% on storage (over time) |
| Use VPC endpoints for S3/DynamoDB | Variable (NAT data costs) |
| Enable CloudFront compression | 30-50% on data transfer |
| Compute Savings Plans | 30-40% on compute |
