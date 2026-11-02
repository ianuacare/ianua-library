# TypeScript patterns (frontend)

Framework-agnostic patterns. Confirm syntax with the **official docs** of the framework in use (React, Vue, Svelte, etc.).

## Component props

- Prefer **explicit prop types** (interfaces or type aliases) exported next to the component.
- Use **`Readonly`** or immutability conventions when the team standard requires it.
- For variants, prefer **discriminated unions** over optional booleans that combine illegally.

```ts
type ButtonProps =
  | { variant: "link"; href: string }
  | { variant: "button"; onClick: () => void };
```

## Generics

- Use generics for **reusable primitives** (lists, data tables) with constraints:

```ts
// Replace the render return type with the framework-specific node type
// (e.g. React.ReactNode, VNode, Snippet, TemplateRef)
interface ListProps<T> {
  items: T[];
  keyFn: (item: T) => string;
  renderItem: (item: T) => unknown;
}
```

## Events and DOM

- Type **event handlers** with the framework's official event types; avoid `any`.
- For wrappers around native elements, use **`ComponentProps`-style** utilities when available (e.g. extend button props while overriding `onClick`).

## Routing

- Use the framework router's **typed routes** or generated types if the project provides them; otherwise document route params explicitly.

## Boundaries and validation

- At system boundaries (API responses, form input, URL params), use **Zod**, **Valibot**, or the project standard: parse unknown data and narrow types before passing to UI code.

## What to avoid

- `any` — use `unknown` and narrow, or proper generics.
- Over-wide props that mirror entire domain models — compose smaller, focused prop interfaces.
- Leaking implementation details in public prop names.
- Framework-specific types in shared utility modules — keep framework coupling at the leaf level.
