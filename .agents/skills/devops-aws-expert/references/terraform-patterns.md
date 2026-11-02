# Terraform Patterns

Reference for `devops-aws-expert` skill — Infrastructure as Code with Terraform.

---

## Project Structure

### Directory-per-environment (recommended for most projects)

```
infrastructure/
├── modules/                    # Reusable modules
│   ├── networking/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── ecs-service/
│   ├── rds/
│   └── monitoring/
├── environments/
│   ├── dev/
│   │   ├── main.tf            # Module calls with dev values
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── providers.tf
│   │   ├── backend.tf         # Remote state config
│   │   └── terraform.tfvars
│   ├── staging/
│   └── production/
└── global/                     # Shared resources (IAM, Route53 zones)
    ├── main.tf
    ├── providers.tf
    └── backend.tf
```

### When to use workspaces vs directories

| Approach | Use when |
|---|---|
| Directory-per-env | Environments differ significantly, need independent state, different approval flows |
| Workspaces | Environments are nearly identical, team is small, rapid iteration |

---

## Remote State Configuration

```hcl
# backend.tf
terraform {
  backend "s3" {
    bucket         = "company-terraform-state"
    key            = "project/env/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    kms_key_id     = "alias/terraform-state"
    dynamodb_table = "terraform-locks"
  }
}
```

**State management rules:**
- One S3 bucket per AWS account for all state files
- DynamoDB table for state locking (prevents concurrent modifications)
- SSE-KMS encryption for state at rest
- Enable S3 versioning for state file recovery
- Never commit `.tfstate` files to git
- Use `data.terraform_remote_state` for cross-stack references

---

## Module Design

```hcl
# modules/ecs-service/variables.tf
variable "service_name" {
  type        = string
  description = "Name of the ECS service"
}

variable "environment" {
  type        = string
  description = "Environment name (dev, staging, production)"
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "tags" {
  type        = map(string)
  description = "Additional tags to apply to all resources"
  default     = {}
}
```

**Module principles:**
- One module per logical component (networking, compute, database)
- Expose only necessary variables — sensible defaults for everything else
- Use `validation` blocks for input constraints
- Output all values that downstream modules or environments might need
- Version modules when shared across repos (git tags or registry)

---

## Variable Organization

```hcl
# variables.tf — organized by category

# --- Required ---
variable "project_name" {
  type        = string
  description = "Project name used in resource naming"
}

variable "environment" {
  type        = string
  description = "Environment name"
}

# --- Optional with defaults ---
variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "eu-west-1"
}

# --- Feature flags ---
variable "enable_nat_gateway" {
  type        = bool
  description = "Enable NAT Gateway for private subnet internet access"
  default     = true
}
```

**Conventions:**
- Group variables: required first, optional with defaults second
- Always include `description`
- Use `type` constraints
- Use `validation` for enums and format checks
- Keep `terraform.tfvars` for environment-specific values only

---

## Naming Conventions

```hcl
locals {
  name_prefix = "${var.project_name}-${var.environment}"

  default_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    CostCenter  = var.cost_center
  }
}

resource "aws_ecs_service" "main" {
  name = "${local.name_prefix}-api"
  tags = merge(local.default_tags, var.tags)
}
```

**Naming rules:**
- Format: `{project}-{environment}-{component}` (e.g., `myapp-prod-api`)
- Lowercase, hyphens as separators
- Keep under 32 characters where possible (some AWS resources have limits)
- Use `local.name_prefix` to ensure consistency
- Apply `local.default_tags` to every resource via `merge()`

---

## Drift Detection

- Run `terraform plan` in CI on schedule (daily) to detect manual changes
- Alert on drift via Slack/email
- Document any manual changes, then import into Terraform

```yaml
# .github/workflows/drift-detection.yml
name: Terraform Drift Detection
on:
  schedule:
    - cron: "0 8 * * 1-5"  # Weekdays at 8 AM
jobs:
  detect-drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init
      - run: terraform plan -detailed-exitcode
        # Exit code 2 = changes detected (drift)
```

---

## Import Existing Resources

```bash
# Import a resource into state
terraform import aws_s3_bucket.main my-existing-bucket

# Generate config for imported resource (Terraform 1.5+)
terraform plan -generate-config-out=generated.tf
```

**Import workflow:**
1. Write the resource block in `.tf` first
2. Run `terraform import` to associate with existing resource
3. Run `terraform plan` to verify no changes
4. Adjust config until plan shows no diff

---

## CI Integration

```yaml
# Terraform CI workflow pattern
jobs:
  terraform:
    steps:
      - name: Format check
        run: terraform fmt -check -recursive

      - name: Init
        run: terraform init -backend-config=backend.hcl

      - name: Validate
        run: terraform validate

      - name: Security scan
        run: tfsec .

      - name: Plan
        run: terraform plan -out=tfplan

      - name: Apply (main branch only)
        if: github.ref == 'refs/heads/main'
        run: terraform apply tfplan
```

**CI rules:**
- Always run `fmt -check`, `validate`, and security scan on PRs
- Save plan output as artifact for apply step
- Apply only on main branch merge (or manual approval)
- Use OIDC for AWS authentication (no long-lived keys)

---

## Common Anti-Patterns

| Anti-pattern | Instead |
|---|---|
| Hardcoded values | Use variables with defaults |
| Monolithic `main.tf` | Split into logical files (`networking.tf`, `compute.tf`) |
| `count` for conditional resources | Use `count` for simple on/off, `for_each` for collections |
| Ignoring state locking | Always use DynamoDB lock table |
| No remote state | Always use S3 backend |
| `terraform apply` locally | Apply only via CI/CD pipeline |
| Using `depends_on` everywhere | Let Terraform infer dependencies from references |
| Wildcard provider versions | Pin provider versions in `required_providers` |

---

## Provider Configuration

```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.default_tags
  }
}
```

- Pin Terraform version and provider versions
- Use `default_tags` in provider to apply tags globally
- Use provider aliases for multi-region setups
