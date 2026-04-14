# DEP-{NNN}: {Deployment Name}

**Date:** {YYYY-MM-DD}
**Author:** {name}
**Environment:** {staging | production}
**Strategy:** {Rolling | Blue-Green | Canary}
**Risk level:** Low | Medium | High

---

## Summary

{Brief description of what is being deployed and why.}

## Changes Included

| Component | Change | PR |
|---|---|---|
| {API service} | {Description} | {#123} |
| {Infrastructure} | {Description} | {#124} |
| {Database migration} | {Description} | {#125} |

## Pre-Deployment Checklist

- [ ] All PRs merged and reviewed
- [ ] CI/CD pipeline passing on main branch
- [ ] Staging deployment validated
- [ ] Database migration tested in staging
- [ ] Snapshots taken of production database
- [ ] Runbooks reviewed and up-to-date
- [ ] Rollback plan documented and tested
- [ ] Stakeholders notified of deployment window
- [ ] On-call engineer available during deployment

## Deployment Steps

### Step 1: Pre-deployment backup

```bash
# Take RDS snapshot
aws rds create-db-snapshot \
  --db-instance-identifier {db-name} \
  --db-snapshot-identifier {db-name}-pre-deploy-{date}
```

### Step 2: Run database migration (if applicable)

```bash
{Migration command}
```

### Step 3: Deploy application

```bash
# Trigger deployment
{Deployment command or describe CI/CD trigger}
```

### Step 4: Verify deployment

```bash
# Check ECS service stability
aws ecs wait services-stable \
  --cluster {cluster-name} \
  --services {service-name}

# Check health endpoint
curl -s https://{domain}/health | jq .
```

### Step 5: Post-deployment validation

- [ ] Health check endpoint returning 200
- [ ] Error rate within normal range (< 1%)
- [ ] Latency within normal range (p99 < 500ms)
- [ ] Key user flows tested manually
- [ ] No unexpected errors in logs

## Rollback Plan

**Trigger rollback if:**
- Error rate > 5% for 5 minutes
- Health check failing for 3+ minutes
- Data integrity issues detected

### Rollback steps:

1. {Step 1 — revert to previous task definition / deployment}
2. {Step 2 — revert database migration if applicable}
3. {Step 3 — verify rollback}
4. {Step 4 — notify stakeholders}

## Monitoring

**Dashboards to watch during deployment:**
- {CloudWatch dashboard link}
- {Grafana dashboard link}

**Key metrics:**
- Error rate (5XX responses)
- Response latency (p50, p95, p99)
- CPU and memory utilization
- Database connections and query latency
- Queue depth (if applicable)

## Communication

| When | Who | Channel |
|---|---|---|
| Deployment start | {team} | {#deployments Slack} |
| Deployment complete | {team} | {#deployments Slack} |
| Rollback triggered | {team + stakeholders} | {#incidents Slack} |

## Post-Deployment

- [ ] Confirm all metrics stable for 30 minutes
- [ ] Remove old task definitions (keep last 5)
- [ ] Update deployment log
- [ ] Close related tickets/issues
