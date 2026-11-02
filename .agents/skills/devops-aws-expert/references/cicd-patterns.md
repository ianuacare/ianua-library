# CI/CD Patterns

Reference for `devops-aws-expert` skill — continuous integration and deployment pipelines.

---

## GitHub Actions with OIDC

Use OIDC for AWS authentication — no long-lived access keys.

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  id-token: write   # Required for OIDC
  contents: read

env:
  AWS_REGION: eu-west-1
  ECR_REPOSITORY: myapp
  ECS_CLUSTER: myapp-production
  ECS_SERVICE: myapp-api

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci
      - run: npm run lint
      - run: npm test

  build-and-push:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    outputs:
      image: ${{ steps.build.outputs.image }}
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-actions-deploy
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to ECR
        id: ecr-login
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push
        id: build
        env:
          REGISTRY: ${{ steps.ecr-login.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          echo "image=$REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG" >> $GITHUB_OUTPUT

  deploy:
    needs: build-and-push
    runs-on: ubuntu-latest
    environment: production  # Requires approval
    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-actions-deploy
          aws-region: ${{ env.AWS_REGION }}

      - name: Deploy to ECS
        run: |
          aws ecs update-service \
            --cluster $ECS_CLUSTER \
            --service $ECS_SERVICE \
            --force-new-deployment
```

**OIDC setup requirements:**
- IAM OIDC identity provider for `token.actions.githubusercontent.com`
- IAM role with trust policy scoped to specific repo/branch
- `id-token: write` permission in workflow

---

## Reusable Workflows

```yaml
# .github/workflows/reusable-deploy.yml
name: Reusable Deploy

on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
      ecs-cluster:
        required: true
        type: string
      ecs-service:
        required: true
        type: string
    secrets:
      aws-role-arn:
        required: true

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.aws-role-arn }}
          aws-region: eu-west-1
      - name: Deploy
        run: |
          aws ecs update-service \
            --cluster ${{ inputs.ecs-cluster }} \
            --service ${{ inputs.ecs-service }} \
            --force-new-deployment
```

```yaml
# .github/workflows/deploy-staging.yml
name: Deploy Staging
on:
  push:
    branches: [main]
jobs:
  deploy:
    uses: ./.github/workflows/reusable-deploy.yml
    with:
      environment: staging
      ecs-cluster: myapp-staging
      ecs-service: myapp-api
    secrets:
      aws-role-arn: ${{ secrets.AWS_STAGING_ROLE_ARN }}
```

---

## Deployment Strategies

### Rolling Deployment (default)

ECS default behavior — gradually replace old tasks with new ones.

```hcl
# ECS service deployment configuration
deployment_minimum_healthy_percent = 50
deployment_maximum_percent         = 200
```

- **Pros**: simple, no extra infrastructure
- **Cons**: both versions serve traffic during rollout
- **Rollback**: deploy previous version

### Blue-Green Deployment

Two identical environments; switch traffic after validation.

```hcl
# Using AWS CodeDeploy with ECS
resource "aws_codedeploy_deployment_group" "main" {
  deployment_group_name  = "myapp-production"
  deployment_config_name = "CodeDeployDefault.ECSAllAtOnce"

  blue_green_deployment_config {
    terminate_blue_instances_on_deployment_success {
      action                           = "TERMINATE"
      termination_wait_time_in_minutes = 60
    }

    deployment_ready_option {
      action_on_timeout = "CONTINUE_DEPLOYMENT"
    }
  }

  ecs_service {
    cluster_name = aws_ecs_cluster.main.name
    service_name = aws_ecs_service.main.name
  }

  load_balancer_info {
    target_group_pair_info {
      prod_traffic_route {
        listener_arns = [aws_lb_listener.https.arn]
      }
      target_group {
        name = aws_lb_target_group.blue.name
      }
      target_group {
        name = aws_lb_target_group.green.name
      }
    }
  }
}
```

- **Pros**: instant rollback, full validation before switch
- **Cons**: double infrastructure during deployment
- **Best for**: production, zero-downtime requirements

### Canary Deployment

Route a small percentage of traffic to the new version first.

- Start with 5-10% traffic to new version
- Monitor error rates and latency
- Gradually increase if metrics are healthy
- Full rollback if anomalies detected

---

## Rollback Strategies

### Automated Rollback

```yaml
# CloudWatch alarm-based rollback
- name: Wait and monitor
  run: |
    sleep 300  # Wait 5 minutes
    ALARM_STATE=$(aws cloudwatch describe-alarms \
      --alarm-names "myapp-error-rate-high" \
      --query 'MetricAlarms[0].StateValue' \
      --output text)
    if [ "$ALARM_STATE" = "ALARM" ]; then
      echo "Error rate too high, rolling back"
      aws ecs update-service \
        --cluster $CLUSTER \
        --service $SERVICE \
        --task-definition $PREVIOUS_TASK_DEF
      exit 1
    fi
```

### Manual Rollback Procedure

1. Identify the previous stable task definition
2. Update ECS service to use previous task definition
3. Monitor health checks and error rates
4. Investigate root cause of failed deployment

---

## Artifact Management

- **Docker images**: ECR with lifecycle policies (keep last N tagged images)
- **Build artifacts**: S3 with lifecycle policy (expire after 90 days)
- **Terraform plans**: store as CI artifacts for audit trail
- **Tag images with git SHA**: enables traceability from deployment to commit

---

## Pipeline Security

- **No long-lived credentials**: use OIDC for AWS, GitHub token for API calls
- **Least-privilege roles**: separate roles for build vs deploy
- **Secret scanning**: run `gitleaks` or `trufflehog` in CI
- **Dependency scanning**: `npm audit`, `trivy` for container images
- **Branch protection**: require PR reviews, passing checks before merge
- **Environment approvals**: manual approval gate for production deployments

---

## Environment Promotion Flow

```
feature branch → PR → main → staging (auto) → production (manual approval)
```

1. **Feature branch**: run tests, lint, security scan
2. **PR to main**: run full test suite, plan infrastructure changes
3. **Merge to main**: auto-deploy to staging
4. **Staging validation**: smoke tests, integration tests
5. **Production**: manual approval, then deploy

---

## GitLab CI Equivalent

```yaml
# .gitlab-ci.yml
stages:
  - test
  - build
  - deploy

test:
  stage: test
  image: node:20-slim
  script:
    - npm ci
    - npm run lint
    - npm test

build:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
  only:
    - main

deploy:
  stage: deploy
  image: amazon/aws-cli:latest
  script:
    - aws ecs update-service --cluster $CLUSTER --service $SERVICE --force-new-deployment
  environment:
    name: production
  when: manual
  only:
    - main
```
