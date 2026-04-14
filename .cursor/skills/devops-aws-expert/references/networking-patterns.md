# Networking Patterns

Reference for `devops-aws-expert` skill — VPC and networking design.

---

## VPC CIDR Planning

### Single-VPC Strategy

```
VPC: 10.0.0.0/16 (65,536 IPs)
├── Public subnets:    10.0.0.0/20, 10.0.16.0/20, 10.0.32.0/20   (3 AZs, 4,096 IPs each)
├── Private subnets:   10.0.48.0/20, 10.0.64.0/20, 10.0.80.0/20  (3 AZs, 4,096 IPs each)
└── Isolated subnets:  10.0.96.0/20, 10.0.112.0/20, 10.0.128.0/20 (3 AZs, 4,096 IPs each)
```

### Multi-VPC / Multi-Account Strategy

```
Production:  10.0.0.0/16
Staging:     10.1.0.0/16
Development: 10.2.0.0/16
Shared:      10.3.0.0/16
```

**Rules:**
- Never overlap CIDR ranges between VPCs that might peer
- Use /16 for VPCs (room to grow)
- Use /20 for subnets (4,096 IPs — enough for most workloads)
- Plan for at least 3 AZs
- Reserve CIDR space for future VPCs

---

## Subnet Strategy

### Three-Tier Subnets

| Tier | Purpose | Route table | NAT | Examples |
|---|---|---|---|---|
| **Public** | Internet-facing resources | IGW route | N/A | ALB, NAT Gateway, Bastion |
| **Private** | Application workloads | NAT GW route | Yes | ECS tasks, Lambda, EC2 apps |
| **Isolated** | Data stores | No internet route | No | RDS, ElastiCache, EFS |

```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.name_prefix}-vpc"
  cidr = "10.0.0.0/16"

  azs              = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
  public_subnets   = ["10.0.0.0/20", "10.0.16.0/20", "10.0.32.0/20"]
  private_subnets  = ["10.0.48.0/20", "10.0.64.0/20", "10.0.80.0/20"]
  database_subnets = ["10.0.96.0/20", "10.0.112.0/20", "10.0.128.0/20"]

  enable_nat_gateway     = true
  single_nat_gateway     = var.environment != "production"  # Cost: 1 NAT for dev, 3 for prod
  one_nat_gateway_per_az = var.environment == "production"

  create_database_subnet_group       = true
  create_database_subnet_route_table = true

  enable_dns_hostnames = true
  enable_dns_support   = true
}
```

---

## NAT Gateway vs NAT Instance

| Factor | NAT Gateway | NAT Instance |
|---|---|---|
| Cost | ~$32/month + data | t3.nano ~$4/month |
| Bandwidth | Up to 100 Gbps | Instance-dependent |
| Availability | Managed, AZ-resilient | Must manage HA yourself |
| Maintenance | None | Patch OS, monitor |
| **Recommendation** | Production | Dev/staging cost savings |

**Production**: one NAT Gateway per AZ for high availability.
**Dev/staging**: single NAT Gateway or NAT Instance to reduce costs.

---

## VPC Endpoints

Avoid NAT Gateway data transfer costs for AWS service traffic.

### Gateway Endpoints (free)

```hcl
# S3 Gateway Endpoint
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = module.vpc.vpc_id
  service_name = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids
}

# DynamoDB Gateway Endpoint
resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id       = module.vpc.vpc_id
  service_name = "com.amazonaws.${var.aws_region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids
}
```

### Interface Endpoints (cost per hour + data)

Create for frequently used services to avoid NAT costs:
- ECR (`ecr.api`, `ecr.dkr`) — required for Fargate image pulls
- CloudWatch Logs (`logs`)
- Secrets Manager (`secretsmanager`)
- SQS (`sqs`)
- KMS (`kms`)

```hcl
resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id             = module.vpc.vpc_id
  service_name       = "com.amazonaws.${var.aws_region}.ecr.api"
  vpc_endpoint_type  = "Interface"
  subnet_ids         = module.vpc.private_subnets
  security_group_ids = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
}
```

**Decision rule**: if monthly NAT data transfer cost > endpoint cost, use endpoints.

---

## VPC Peering vs Transit Gateway

| Factor | VPC Peering | Transit Gateway |
|---|---|---|
| Connections | 1-to-1 (max 125 per VPC) | Hub-and-spoke (thousands) |
| Cost | Free (data transfer only) | $0.05/hr + data transfer |
| Transitive routing | No | Yes |
| Cross-region | Yes | Yes |
| **Use when** | 2-3 VPCs | 4+ VPCs, complex routing |

### VPC Peering Setup

```hcl
resource "aws_vpc_peering_connection" "prod_to_shared" {
  vpc_id        = module.prod_vpc.vpc_id
  peer_vpc_id   = module.shared_vpc.vpc_id
  auto_accept   = true
}

# Route from prod to shared
resource "aws_route" "prod_to_shared" {
  route_table_id            = module.prod_vpc.private_route_table_ids[0]
  destination_cidr_block    = module.shared_vpc.vpc_cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.prod_to_shared.id
}
```

---

## Route53

### Routing Policies

| Policy | Use case |
|---|---|
| Simple | Single resource |
| Weighted | A/B testing, gradual migration |
| Latency | Multi-region, route to closest |
| Failover | Active-passive DR |
| Geolocation | Compliance, region-specific content |

### Common DNS Patterns

```hcl
# ALB alias record
resource "aws_route53_record" "api" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "api.example.com"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# CloudFront alias
resource "aws_route53_record" "cdn" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "example.com"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}
```

- Use alias records for AWS resources (no TTL charge, health checks)
- Set low TTL (60s) during migrations, higher (300s) for stable records
- Use private hosted zones for internal service discovery

---

## VPN and Direct Connect

### Site-to-Site VPN

- Use for connecting on-premises network to AWS VPC
- Two tunnels for redundancy (active/passive)
- Cost: ~$36/month per VPN connection
- Bandwidth: up to 1.25 Gbps per tunnel

### Direct Connect

- Dedicated network connection from on-premises to AWS
- Consistent latency, higher bandwidth (1-100 Gbps)
- Cost: port fee + data transfer
- Use for: large data transfers, latency-sensitive workloads, hybrid architectures

---

## Load Balancer Selection

| Type | Use case | Layer |
|---|---|---|
| **ALB** | HTTP/HTTPS, path routing, gRPC | Layer 7 |
| **NLB** | TCP/UDP, ultra-low latency, static IPs | Layer 4 |
| **GLB** | Third-party appliances | Layer 3 |

**ALB is the default choice** for web applications. Use NLB only for non-HTTP protocols or when you need static IPs / extreme performance.
