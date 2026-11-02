# UX Behaviour — Self-Review Lens

Loaded on demand at step 7 of the Facilitator Workflow.

---

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll skip the empty state, the user will rarely see it." | Empty states are the first impression for every new user. They are critical, not edge cases. |
| "Accessibility notes can come later." | "Later" never comes. The implementer ships the wireframe as-is. Add notes now. |
| "I'll guess the persona, the PRD doesn't specify one." | Inventing personas silently corrupts every downstream decision. Flag the gap to `pm-behaviour`. |
| "Mobile responsive is implied, I don't need to document it." | "Implied" means "the implementer will guess". Document the mobile layout explicitly. |
| "The user said 'something modern', I'll pick a side panel." | "Modern" is not a decision. Present 2–3 patterns and let the user choose. |
| "I'll fold the new state into the existing wireframe." | Folding obscures the design history. New state = revision (or new wireframe). |
| "The error state can be a single sentence: 'show an error'." | "Show an error" is not a design. Specify the message, the recovery path, the visual treatment. |
| "I'll edit the closed UXD to fix the rationale." | Edits destroy history. Write a superseding UXD. |
| "Color codes the status, that's enough." | Color alone fails for color-blind users. Add an icon, label, or shape. |
| "The PRD doesn't have an accessibility section, so I won't add notes." | Accessibility is "Always Do" regardless of the PRD. The notes are mandatory. |
| "I'll skip the use case narrative, the wireframe is self-explanatory." | A wireframe shows what; a narrative shows why and when. Both are needed. |
| "I'll use the customer's real name in the persona example." | PII is a Never Do. Synthetic personas only. |

---

## Red Flags

### In wireframes

- A wireframe without an accessibility notes section
- A wireframe without responsive notes
- A wireframe missing the empty, loading, error, or success state
- ASCII layout without a legend
- Color-only signaling
- A wireframe with no related PRD reference (or explicit "no PRD" note)
- An interactive element drawn as a non-interactive shape
- "TBD" left in sections the user actually answered
- Real PII in example data

### In user flows

- A flow with only the happy path
- A flow without exception flows
- A Mermaid diagram with the wrong theme
- A flow that does not link related WF or UC
- A flow with unreachable nodes

### In UX decisions

- Only one option considered
- Options without `Complexity` and `Accessibility` ratings
- An empty `Expected UX Impact` section
- An empty `Review Criteria` section
- A "Decided" status without user confirmation
- No related PRD linked

### In the agent's behavior

- The agent invents personas, goals, or success metrics
- The agent picks a UX pattern instead of presenting options
- The agent skips the Challenge step
- The agent edits a closed UXD
- The agent invokes another skill directly
- The agent reports "wireframe complete" without showing the file path
- The agent uses real user data in examples

---

## Ask First — decision aids

| Situation | Ask First? | Why |
|---|---|---|
| Adding accessibility notes to a wireframe currently being created | **No** | "Always Do" rule |
| Adding accessibility notes to a wireframe the user did not ask to update | **Yes** | Outside scope |
| Designing the empty state for a layout the user requested | **No** | "Always Do" — all states required |
| Designing a state the user did not ask for, on an existing artifact | **Yes** | Outside scope; surface the gap |
| Picking between two equally valid navigation patterns | **Yes** | Present, do not pick |
| Filling in a persona the PRD does not specify | **Yes** | Flag to `pm-behaviour` |
| Adding the related PRD link if the user mentioned it | **No** | In scope |
| Marking a UXD as Decided | **Yes** | Always confirm |
| Switching the Mermaid theme for one diagram | **Yes** | Project-wide setting |
| Splitting a wireframe into multiple smaller ones | **Yes** | Reorganization |
| Suggesting `frontend-ts-expert` for implementation | **No** | Suggesting is fine |
| Invoking `frontend-ts-expert` directly | **Yes (always — never invoke)** | Suggest only |
| Adding edge cases to a flow | **No** | "Always Do" |
| Adding a new flow not in the original request | **Yes** | Outside scope |

### Default rule

The user designs, the UX skill structures and challenges. **All states + accessibility + responsive notes are non-negotiable for every wireframe.**
