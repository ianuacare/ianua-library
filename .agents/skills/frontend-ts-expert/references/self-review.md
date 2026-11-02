# Frontend TypeScript — Self-Review Lens

Loaded on demand at step 10 of the Workflow. Three tools to use before declaring "done":

1. **Common Rationalizations** — meta-cognitive patterns that precede a rule violation
2. **Red Flags** — observable signals in the diff, behavior, and runtime
3. **Ask First decision aids** — concrete examples for the most fragile boundary tier

---

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "It's just a UI tweak, I'll skip the test." | UI tweaks regress visually and silently. The test catches it the next time someone touches the component. |
| "The empty state is unlikely, I'll skip it." | Empty states are the single most common bug in production UIs. Implement it. |
| "I'll add the loading state in a follow-up." | "Follow-up" never comes. Users see the half-finished version in production. |
| "Coverage 80% is arbitrary, this component is simple." | Simple components have edge cases too (long text, wrapping, RTL, zoomed font). |
| "I'll use `any` here, the prop type is too complex." | If the prop type is complex, the component is doing too much. Split it. |
| "The framework's example used `useEffect` like this, I'll copy it." | Framework examples are intentionally simplified. Verify the version, the dependency array, and the cleanup. |
| "I'll skip the screen reader test, it works for me." | "Works for me" is not accessibility. Test with the actual assistive tech or at least a tool. |
| "The wireframe doesn't show this state, I'll invent it." | Inventing UX silently is a Never Do. Flag the gap to `ux-behaviour`. |
| "I'll commit the broken style and fix it next." | Broken styles in main are a cost on every following commit. Fix or revert. |
| "I'll add the JSDoc later." | "Later" never comes. The component is consumed before then. |
| "The `// @ts-ignore` will be temporary." | Temporary ts-ignores become permanent. Type the thing or extract it. |
| "I don't need to update the spec, the change is small." | Small changes accumulate into stale specs. The spec is part of the deliverable. |
| "I'll inline the secret in the API URL for now." | Frontend code ships to clients. There is no "for now" — it's leaked the moment it builds. |
| "The design token doesn't have the exact shade I need, I'll hardcode it." | Propose a new token. Hardcoded values erode the system one hex at a time. |
| "This component is page-specific, I don't need to put it in the library." | If it has visual identity (buttons, cards, inputs), it belongs in `{components_path}`. Page-specific = layout composition, not visual atoms. |

---

## Red Flags

### In the diff

- A new component without a corresponding test in the same diff
- A new exported symbol with no JSDoc/TSDoc
- An `any` type added (even one)
- A `// @ts-ignore` without inline justification
- A `// TODO: handle empty state` comment
- A `dangerouslySetInnerHTML` (or framework equivalent) without sanitization
- A new dependency in `package.json` not justified in the PR
- A spec file's `Current implementation` path that does not exist
- A CHANGELOG entry missing for a public API change
- A hex color or magic number that should reference design tokens
- A component in a page directory that duplicates one in `{components_path}`
- A hardcoded color/spacing literal in a project that has `{design_tokens_path}` configured
- An animation without `prefers-reduced-motion` handling
- A button or interactive element built from `<div>` instead of `<button>`
- A click handler on a non-focusable element

### In the agent's behavior

- The agent says "I'll add tests in a follow-up"
- The agent skips loading/empty/error states
- The agent invents UX details not present in the wireframe
- The agent reaches for `any` instead of asking
- The agent adds a new state-management library without warning
- The agent reports "done" without test/type-check output
- The agent edits files outside the requested scope without asking

### In the running code

- Layout shift on mount (CLS regression)
- Console errors or warnings on render
- Focus trap missing in modal/dialog
- Tab order broken or unexpected
- Long lists rendering all items at once (no virtualization)
- Network waterfall: avoidable sequential fetches
- Images without `alt` attributes
- Form fields without `<label>` or `aria-label`

---

## Ask First — decision aids

| Situation | Ask First? | Why |
|---|---|---|
| Adding `swr` to a project that already uses `react-query` | **Yes** | Replacing the project standard for data fetching |
| Adding a `@types/*` package for an already-used dependency | **No** | Type-only |
| Adding a transitive peer dependency required by an installed package | **No** | Not a real choice |
| Changing CSS Modules to Tailwind in code outside the requested scope | **Yes** | Project-wide styling decision |
| Adding Tailwind classes to a new component in a Tailwind project | **No** | "Always Do" rule |
| Renaming a component file (touches every importer) | **Yes** | Outside scope, broad blast radius |
| Renaming a private hook used only inside one file | **No** | Local refactor |
| Splitting a 400-line component into smaller pieces because the user asked for "a small change" | **Yes** | Outside requested scope |
| Splitting a 400-line component because the user asked to "refactor for readability" | **No** | In scope by request |
| Adding a `<title>` or meta tags on a page | **Yes** | Coordinate with `seo-expert` for indexable pages |
| Bumping a framework major version | **Yes** | Likely breaking changes |
| Bumping a patch version | **No** | Routine |
| Filling in a state the wireframe does not show (loading/empty/error) | **Yes** | Coordinate with `ux-behaviour`; do not invent |
| Adding the missing accessibility label to an existing button | **No** | "Always Do" rule applies |
| Adding a new design token to `{design_tokens_path}` | **Yes** | Tokens are a shared system; additions affect the entire project |
| Using an existing design token in a new component | **No** | Encouraged |

### Default rule

If the change is **inside the file or component being actively edited** AND covered by an "Always Do" rule, proceed. Otherwise, when in doubt, ask. Never invent UX.
