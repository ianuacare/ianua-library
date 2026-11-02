# ARCH-{NNN}: {Architecture Name}

**Date:** {YYYY-MM-DD}
**Author:** {name}
**Status:** Draft | Reviewed | Approved
**Environment:** {dev | staging | production}

---

## Overview

{Brief description of the architecture and its purpose.}

## Architecture Diagram

```mermaid
graph TB
    {Replace with actual architecture diagram}
```

## AWS Services

| Service | Resource | Configuration | Purpose |
|---|---|---|---|
| {ECS Fargate} | {myapp-api} | {0.5 vCPU, 1GB, 2 tasks} | {API server} |
| {RDS} | {myapp-db} | {db.t3.medium, Multi-AZ} | {Primary database} |
| {ElastiCache} | {myapp-cache} | {cache.t4g.micro} | {Session cache} |

## Network Design

| Subnet tier | CIDR | Resources |
|---|---|---|
| Public | {10.0.0.0/20} | {ALB, NAT Gateway} |
| Private | {10.0.48.0/20} | {ECS tasks} |
| Isolated | {10.0.96.0/20} | {RDS, ElastiCache} |

## Security Posture

- **IAM:** {Description of IAM roles and policies}
- **Encryption:** {At rest and in transit details}
- **Network:** {Security groups, NACLs, WAF}
- **Secrets:** {How secrets are managed}

## Cost Estimate

| Service | Configuration | Monthly cost |
|---|---|---|
| {ECS Fargate} | {2 tasks, 0.5 vCPU} | {$45} |
| {RDS} | {db.t3.medium, Multi-AZ} | {$140} |
| {ElastiCache} | {cache.t4g.micro} | {$15} |
| {NAT Gateway} | {1x + data} | {$40} |
| {CloudFront} | {10 GB/month} | {$2} |
| **Total** | | **${total}** |

## Scaling Strategy

- **Compute:** {Auto-scaling policy — min/max/target}
- **Database:** {Vertical scaling plan, read replicas if needed}
- **Cache:** {Scaling approach}

## Disaster Recovery

- **RPO:** {target}
- **RTO:** {target}
- **Strategy:** {Backup & Restore | Pilot Light | Warm Standby}
- **Backup:** {What is backed up, retention, cross-region}

## Well-Architected Review

| Pillar | Status | Notes |
|---|---|---|
| Operational Excellence | {OK / Concern} | {Notes} |
| Security | {OK / Concern} | {Notes} |
| Reliability | {OK / Concern} | {Notes} |
| Performance Efficiency | {OK / Concern} | {Notes} |
| Cost Optimization | {OK / Concern} | {Notes} |
| Sustainability | {OK / Concern} | {Notes} |

## Open Questions

- [ ] {Question 1}
- [ ] {Question 2}

## Related

- Decision records: {INFRA-NNN}
- Runbooks: {RUN-NNN}
- Implementation PR: {link}
