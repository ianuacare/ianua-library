# {UC-NNN} — {Use Case Title}

| Field | Value |
|-------|-------|
| **Author** | {name} |
| **Date** | {YYYY-MM-DD} |
| **Status** | Draft / In Review / Approved / Superseded |
| **Related PRD** | {PRD-NNN if applicable} |

## Summary

One-paragraph description of this use case and the value it delivers.

## Actor

| Field | Value |
|-------|-------|
| **Primary actor** | {user persona or role} |
| **Secondary actors** | {other users or systems involved} |

## Goal

What does the primary actor want to achieve? State it in one sentence from the actor's perspective.

## Preconditions

- {condition that must be true before this use case can begin}
- {another precondition}

## Trigger

What event or action initiates this use case?

## Main Success Scenario

| Step | Actor | Action |
|------|-------|--------|
| 1 | {actor} | {action} |
| 2 | System | {response} |
| 3 | {actor} | {action} |
| 4 | System | {response} |
| 5 | {actor} | {action} |

## Alternative Flows

### Alt-1: {alternative name} (branches from Step {N})

| Step | Actor | Action |
|------|-------|--------|
| {N}a.1 | {actor} | {action} |
| {N}a.2 | System | {response} |

_Rejoins main scenario at Step {M} / Ends here._

### Alt-2: {alternative name} (branches from Step {N})

| Step | Actor | Action |
|------|-------|--------|
| {N}a.1 | {actor} | {action} |
| {N}a.2 | System | {response} |

_Rejoins main scenario at Step {M} / Ends here._

## Exception Flows

### Exc-1: {exception name} (at Step {N})

| Step | Actor | Action |
|------|-------|--------|
| {N}e.1 | System | {error detection} |
| {N}e.2 | System | {error message / recovery action} |

_Outcome: {how the flow ends or recovers}._

## Postconditions

### On Success

- {system state after successful completion}
- {data changes, notifications, etc.}

### On Failure

- {system state if the use case fails}
- {rollback, error logging, etc.}

## Business Rules

- {rule 1: constraint or validation that applies during this use case}
- {rule 2: another relevant rule}

## UX Notes

- {interaction pattern considerations}
- {accessibility requirements}
- {feedback or confirmation patterns}

## References

- Related PRD: {link to PRD-NNN if applicable}
- Related wireframe: {link to WF-NNN if applicable}
- Related flow: {link to FLOW-NNN if applicable}
- Related UX decision: {link to UXD-NNN if applicable}
