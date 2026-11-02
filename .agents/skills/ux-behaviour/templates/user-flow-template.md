# {FLOW-NNN} — {Flow Title}

| Field | Value |
|-------|-------|
| **Author** | {name} |
| **Date** | {YYYY-MM-DD} |
| **Status** | Draft / In Review / Approved / Superseded |
| **Related PRD** | {PRD-NNN if applicable} |

## Purpose

What user goal does this flow describe? What process does it map?

## Actors

| Actor | Role | Description |
|-------|------|-------------|
| {actor} | Primary / Secondary / System | {brief description} |

## Preconditions

- {condition that must be true before the flow starts}
- {another precondition}

## Flow Diagram

```mermaid
%%{init: {'theme': 'neutral'}}%%
flowchart TD
    A[Start: {trigger}] --> B{Decision point?}
    B -->|Yes| C[Action 1]
    B -->|No| D[Action 2]
    C --> E[Action 3]
    D --> E
    E --> F{Another decision?}
    F -->|Success| G[Happy path outcome]
    F -->|Error| H[Error handling]
    H --> I[Recovery action]
    I --> E
    G --> J[End: {outcome}]
```

## Steps Detail

### Happy Path

| Step | Actor | Action | System Response | Notes |
|------|-------|--------|-----------------|-------|
| 1 | {actor} | {action} | {response} | {notes} |
| 2 | {actor} | {action} | {response} | {notes} |

### Alternative Flows

#### Alt-1: {alternative scenario name}

- **Trigger**: {what causes this alternative}
- **Steps**: {how it diverges from the happy path}
- **Rejoins at**: Step {N} / End

#### Alt-2: {alternative scenario name}

- **Trigger**: {what causes this alternative}
- **Steps**: {how it diverges}
- **Rejoins at**: Step {N} / End

### Exception Flows

#### Exc-1: {exception scenario name}

- **Trigger**: {error or unexpected condition}
- **Steps**: {error handling sequence}
- **Outcome**: {how the flow ends or recovers}

## Postconditions

- {state of the system after the flow completes successfully}
- {data changes, notifications sent, etc.}

## Edge Cases

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 1 | {edge case} | {how the system handles it} |
| 2 | {edge case} | {behavior} |

## References

- Related PRD: {link to PRD-NNN if applicable}
- Related wireframe: {link to WF-NNN if applicable}
- Related use case: {link to UC-NNN if applicable}
- Related UX decision: {link to UXD-NNN if applicable}
