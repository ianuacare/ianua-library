# DevOps AWS — Self-Review Lens

Loaded on demand at step 8 of the Execution Workflow. Three tools to use before declaring "done":

1. **Common Rationalizations** — meta-cognitive patterns that precede a rule violation
2. **Red Flags** — observable signals in IaC, behavior, and runtime
3. **Ask First decision aids** — concrete examples for the most fragile boundary tier

---

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll just click this in the console, IaC later." | "Later" never comes. The console change drifts from IaC and breaks the next `terraform apply`. |
| "It's a tiny IAM `*` to make it work, I'll tighten it later." | The `*` policy is the one that gets exploited. There is no "later" — fix it now or do not deploy. |
| "Encryption is overkill for this dev RDS instance." | Dev databases get production data copied into them constantly. Encrypt by default. |
| "I'll skip the cost estimate, it's small." | "Small" resources accumulate. The cost estimate takes 60 seconds and prevents next month's surprise. |
| "I'll deploy first and add monitoring after." | Monitoring after means the first incident is invisible. Alarms ship in the same PR as the resource. |
| "I'll commit the state file just this once." | The state file contains secrets and locks. Once in git, it's leaked forever. |
| "The plan output looks fine, I don't need to read every line." | The destroy hidden in line 47 is the one that takes prod down. Read every `-` and every `~`. |
| "I'll skip the backup before this migration, it's just a column rename." | "Just a column rename" is how data loss starts. Backup, then change. |
| "The runbook can wait." | The runbook prevents the 3am page from becoming a 6am outage. Write it now. |
| "I'll use the root account, it's faster." | Root account = no audit trail, no MFA boundary, no IAM. Never. |
| "I'll widen the security group to debug, then narrow it." | Wide security groups in production are how breaches happen. Use Session Manager, VPC endpoints, or a bastion. |
| "0.0.0.0/0 on this port is fine, it's behind WAF." | WAF is layer 7. The port is layer 4. Rotate ports, restrict by SG, then add WAF. |

---

## Red Flags

### In the IaC diff

- A `*` in any IAM `Action` or `Resource`
- A new ingress rule with `0.0.0.0/0` on any port except 443 on a load balancer
- A resource without all 4 mandatory tags
- A stateful resource (`aws_db_instance`, `aws_dynamodb_table`, `aws_s3_bucket`) with encryption disabled or unset
- A `deletion_protection = false` on a production database
- A hardcoded credential, token, ARN containing an account ID, or password
- A state file (`*.tfstate`) added to git
- A new resource without a corresponding CloudWatch alarm
- A `terraform destroy` in a CI script without manual approval gate
- A new RDS/Aurora instance without `Multi-AZ` in production
- A Lambda function without `dead_letter_config`
- A `lifecycle { prevent_destroy = true }` removed in a diff

### In the agent's behavior

- The agent runs `terraform apply` without showing the plan first
- The agent says "I'll add monitoring in a follow-up PR"
- The agent reaches for `*` in IAM instead of enumerating actions
- The agent skips the cost estimate
- The agent skips the security scan
- The agent introduces a new IaC tool without warning the user
- The agent edits resources outside the requested scope without asking
- The agent declares "done" without showing the plan output

### In the running infrastructure

- An EC2 instance with a public IP that should not have one
- A security group with `0.0.0.0/0` on port 22
- An S3 bucket with public ACLs or no Block Public Access
- An RDS instance reachable from the public internet
- A CloudWatch log group with no retention policy
- An IAM user with console access and no MFA
- A KMS key without rotation enabled
- A snapshot retention period of 0 days

---

## Ask First — decision aids

| Situation | Ask First? | Why |
|---|---|---|
| Provisioning a `db.r6g.xlarge` RDS instance | **Yes** | >$200/month |
| Provisioning a `db.t4g.micro` RDS instance for dev | **No** | <$20/month, in scope |
| Adding `0.0.0.0/0:443` ingress to an ALB | **No** | "Always Do" rule covers this |
| Adding `0.0.0.0/0:22` ingress anywhere | **Yes** | Always wrong; propose Session Manager instead |
| Adding `0.0.0.0/0:5432` to an RDS SG | **Yes** | Should never happen; propose VPC peering or PrivateLink |
| Creating a new IAM role with a tightly-scoped policy | **No** | "Always Do" applies |
| Creating an IAM role with `Action: "*"` | **Yes** | Even temporarily, propose alternatives |
| Running `terraform apply` against `dev` | **No** | Routine, but show plan first |
| Running `terraform apply` against `production` | **Yes** | Always |
| Running `terraform destroy` against `dev` | **Yes** | Confirm resource list |
| Running `terraform destroy` against `production` | **Yes (always)** | Confirm in writing, twice |
| Adding a new tag to all resources | **Yes** | Touches every resource |
| Adding a new tag to one new resource | **No** | In scope |
| Switching from Terraform to CDK | **Yes** | Project-wide tool change |
| Bumping a Terraform provider patch version | **No** | Routine |
| Bumping a Terraform provider major version | **Yes** | Likely breaking |
| Adding a new VPC | **Yes** | Architectural decision; write `INFRA-NNN` |
| Adding a new subnet to an existing VPC | **No (with plan review)** | In scope |
| Increasing RDS storage by 10% | **No (with plan review)** | Routine |
| Modifying RDS instance class | **Yes** | Causes restart, possible downtime |
| Adding a CloudWatch alarm to a new resource | **No** | "Always Do" rule applies |
| Removing a CloudWatch alarm | **Yes** | Reduces observability |
| Setting up a new GitHub Actions OIDC role | **Yes** | New trust boundary |

### Default rule

If the change is **routine, scoped, and within the four mandatory tags + encryption + private-by-default rules**, proceed (after showing the plan). Otherwise, ask. **Production changes always require an explicit go-ahead, no exceptions.**
