# RUN-{NNN}: {Service Name} — {Issue Type}

**Last updated:** {YYYY-MM-DD}
**Service:** {service name}
**Owner:** {team/person}
**Severity:** P0 | P1 | P2 | P3

---

## Symptoms

- **Alert:** {CloudWatch alarm name and link}
- **User impact:** {What users experience}
- **Dashboard:** {Link to CloudWatch/Grafana dashboard}
- **Metrics to check:** {Which metrics indicate this issue}

## Diagnosis

### Step 1: Check service health

```bash
aws ecs describe-services \
  --cluster {cluster-name} \
  --services {service-name} \
  --query 'services[0].{status:status,running:runningCount,desired:desiredCount}'
```

### Step 2: Check logs

```bash
aws logs tail /ecs/{service-name} \
  --filter-pattern "ERROR" \
  --since 30m \
  --format short
```

### Step 3: Check downstream dependencies

```bash
# Database connectivity
aws rds describe-db-instances \
  --db-instance-identifier {db-name} \
  --query 'DBInstances[0].DBInstanceStatus'

# Cache status
aws elasticache describe-replication-groups \
  --replication-group-id {cache-name} \
  --query 'ReplicationGroups[0].Status'
```

## Resolution

### Scenario A: {High error rate from application bugs}

1. {Step 1 — identify the failing endpoint/component}
2. {Step 2 — check recent deployments}
3. {Step 3 — rollback if recent deployment caused issue}

```bash
# Rollback to previous task definition
aws ecs update-service \
  --cluster {cluster-name} \
  --service {service-name} \
  --task-definition {previous-task-def-arn}
```

### Scenario B: {Resource exhaustion (CPU/memory)}

1. {Step 1 — verify CPU/memory metrics}
2. {Step 2 — check for traffic spike or memory leak}
3. {Step 3 — scale up tasks}

```bash
# Scale up ECS service
aws ecs update-service \
  --cluster {cluster-name} \
  --service {service-name} \
  --desired-count {new-count}
```

### Scenario C: {Downstream dependency failure}

1. {Step 1 — identify which dependency is failing}
2. {Step 2 — check dependency health}
3. {Step 3 — mitigation steps}

## Rollback

1. Identify the last known good task definition:
   ```bash
   aws ecs list-task-definitions \
     --family-prefix {task-family} \
     --sort DESC \
     --max-items 5
   ```

2. Update service to use previous task definition:
   ```bash
   aws ecs update-service \
     --cluster {cluster-name} \
     --service {service-name} \
     --task-definition {previous-task-def}
   ```

3. Verify rollback:
   ```bash
   aws ecs wait services-stable \
     --cluster {cluster-name} \
     --services {service-name}
   ```

## Escalation

| Condition | Action |
|---|---|
| Not resolved in 15 minutes | Contact {senior engineer / team lead} |
| Data loss suspected | Page {database owner} immediately |
| Multiple services affected | Declare incident, notify {stakeholders} |

**Escalation contacts:**
- Primary: {name, contact}
- Secondary: {name, contact}
- Management: {name, contact}

## Post-Incident

- [ ] Create incident report
- [ ] Update this runbook with new findings
- [ ] Create tickets for preventive measures
- [ ] Update monitoring/alerting if gaps found
- [ ] Schedule post-mortem meeting

## Revision History

| Date | Author | Change |
|---|---|---|
| {YYYY-MM-DD} | {name} | Initial version |
