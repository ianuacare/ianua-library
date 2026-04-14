# Ship — Pre-Launch Checklist and Deployment

Run the pre-launch checks, prepare the deployment, commit the release, and update the issue tracker. Orchestrates three skills in sequence.

## Sequence

### 1. Pre-launch verification (`devops-aws-expert`)

Load `.cursor/skills/devops-aws-expert/SKILL.md` and run its full Verification checklist against the changes:

- IaC plan reviewed (`terraform plan` / `cdk diff`)
- Security scan (`tfsec` / `checkov`) — zero High/Critical
- Cost estimate produced
- All resources tagged
- Encryption verified for new stateful resources
- CloudWatch alarms in place for new production services
- Runbook drafted for new services
- Mermaid architecture diagram updated
- `INFRA-NNN` decision record created if architectural choice was made
- Backup taken for any stateful resource being modified

The skill's **Always Do**, **Ask First**, and **Never Do** boundaries apply throughout. Production changes require explicit user confirmation per the skill's Ask First tier.

### 2. Commit (`commit-manager`)

Once pre-launch checks pass, **suggest** committing via `commit-manager`. Do not auto-commit.

```
"All pre-launch checks pass. Would you like me to commit the changes via commit-manager?"
```

If the user confirms, load `.cursor/skills/commit-manager/SKILL.md` and run the commit workflow.

### 3. Issue lifecycle (`pm-github-workflow`)

After the commit, **suggest** updating the related issue status to `In review` via `pm-github-workflow`. Do not auto-update.

```
"Commit done. Would you like me to update issue #N to 'In review' via pm-github-workflow?"
```

## What /ship never does

- **Never** runs `git push` (commit-manager forbids it)
- **Never** sets an issue to `Done` (only the user can, via `pm-github-workflow`)
- **Never** runs `terraform apply` against production without explicit user confirmation
- **Never** auto-deploys without showing the plan first
- **Never** silently skips a Verification check

## Disqualifying signals (block the ship)

Any of these block the deployment:

- A failing security scan finding
- A missing CloudWatch alarm on a new production service
- A missing runbook for a new production service
- A failing test from `/test` that has not been fixed
- A failing critical finding from `/review`
- A missing `INFRA-NNN` for an architectural change
