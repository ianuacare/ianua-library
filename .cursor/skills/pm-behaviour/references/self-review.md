# PM Behaviour — Self-Review Lens

Loaded on demand at step 7 of the Facilitator Workflow. Three tools to use before declaring "done":

1. **Common Rationalizations** — meta-cognitive patterns that precede a rule violation
2. **Red Flags** — observable signals in PRDs, decisions, and prioritization
3. **Ask First decision aids** — concrete examples for the most fragile boundary tier

---

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The user implied this acceptance criterion, I'll just write it." | "Implied" is the agent's interpretation, not the user's input. Ask. |
| "RICE says this feature wins, I'll mark it as the priority." | The framework informs, the user decides. Present the score, do not pick. |
| "I'll fill the success metrics with reasonable defaults." | Success metrics drive every downstream decision. Inventing them silently is harmful. Ask or mark TBD. |
| "The user said 'do whatever makes sense' for prioritization." | "Whatever makes sense" is not a decision. Present 2–3 options with scores and let the user choose. |
| "I'll skip the Risks section, this feature looks safe." | Every feature has risks. Listing none is itself a Red Flag. |
| "The PRD is small, I don't need to write a DEC." | Small features still embed decisions (scope, target user, metric). The DEC takes 5 minutes. |
| "I'll create the GitHub issues now since the PRD is approved." | Issue creation is `pm-github-workflow`'s job, on user request. Suggest. |
| "I'll fold the new requirement into the existing PRD instead of writing a new one." | Folding obscures history. New requirement = new PRD or explicit superseding revision. |
| "The user contradicted yesterday's decision, I'll just update the old DEC." | Edits destroy history. Write a superseding DEC. |
| "I'll skip the Challenge step, the user is in a hurry." | The Challenge step is the entire value of the PM facilitator. Skipping it makes the skill ornamental. |
| "I'll guess the effort estimate to keep things moving." | Effort estimates come from the relevant expert skill or the user. Mark TBD. |
| "I'll use real customer names in the example user stories." | PII is a Never Do, even in examples. Use synthetic personas. |

---

## Red Flags

### In PRDs

- A PRD with no user research, evidence, or explicit "no data available" note
- A PRD with placeholder text in any section
- A PRD whose Acceptance Criteria are vague ("works well", "fast")
- A PRD that lists no risks or assumptions
- Success metrics that are not measurable
- A "Done" status set without user confirmation
- Personas that are obviously generic ("user", "customer") instead of specific
- A PRD that does not link any UX, frontend, or backend work even though it should

### In Decisions

- Only one option considered
- Options without Effort estimates
- A decision marked "Decided" before user confirmation
- An "Evidence" section left empty without acknowledging the gap
- A decision that contradicts a previous DEC without superseding it
- Cross-references missing to related PRD-NNN

### In the agent's behavior

- The agent picks a winner from a prioritization framework instead of asking
- The agent writes a PRD section without asking the user
- The agent skips the Challenge step
- The agent auto-creates GitHub issues
- The agent edits a closed PRD or DEC instead of writing a new one
- The agent invents personas, metrics, or risks
- The agent reports "PRD complete" without showing the file path

---

## Ask First — decision aids

| Situation | Ask First? | Why |
|---|---|---|
| Filling Acceptance Criteria the user provided in the request | **No** | Direct user input |
| Filling Acceptance Criteria the user did not mention | **Yes** | Ask, do not assume |
| Picking the highest RICE score as the priority | **Yes** | Present, do not pick |
| Picking the highest RICE score after the user said "I trust the framework" | **No** | Explicit waiver |
| Marking a PRD as Decided | **Yes** | Always confirm |
| Updating a PRD's status from Draft to Decided | **Yes** | Status is a user decision |
| Adding a new section to a PRD per user request | **No** | In scope |
| Splitting a PRD into multiple | **Yes** | Reorganization |
| Suggesting `pm-github-workflow` to create issues | **No** | Suggesting is "Always Do" |
| Creating GitHub issues directly | **Yes (always — never invoke)** | Not allowed at all |
| Suggesting `data-retriever` for evidence | **No** | Suggesting is fine |
| Invoking `data-retriever` directly | **Yes (always — never invoke)** | Suggest only |
| Filling Success Metrics from the PRD template defaults | **Yes** | Defaults are placeholders |
| Filling Risks based on common patterns ("execution risk", "adoption risk") | **Yes** | Even common patterns need user validation |
| Adding a note that data is unavailable | **No** | Better than silence |
| Suggesting a release plan structure | **No** | Suggesting is fine |

### Default rule

The user makes the call. The PM presents options, scores, frameworks, and templates. When in doubt, ask. **The Challenge step is non-negotiable.**
