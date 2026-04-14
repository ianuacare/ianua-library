# Audit SEO — Search Engine Audit and Strategy

Run a technical or content SEO audit grounded in Google Search Central guidance.

**This command activates the `seo-expert` skill.** Load and execute `.cursor/skills/seo-expert/SKILL.md`.

The skill follows a facilitator workflow: every recommendation cites a Google Search Central URL, distinguishes brand vs non-brand and search intent, never invents Google guidance, and never recommends deceptive structured data. Outputs are saved under `docs/specs/seo/`.

## Modes

The skill asks which mode at the start:

- **Audit** — produce a `SEO-NNN` audit covering crawl/index signals, on-page, structured data, experience signals, and prioritized actions
- **Strategy** — produce a `SEOS-NNN` strategy with goals, topics/keywords, workstreams, and KPIs
- **Decision** — record a `SEOD-NNN` decision (URL strategy, indexing policy, schema approach, etc.)
- **Structured data review** — walk the structured data checklist for a specific page or template

## Prerequisites

For audits, agree the scope (site / template / URL list) and what data is available (Search Console, server logs, staging environment).

## Suggested next steps after /audit-seo

- Indexing-affecting changes → `/decide` (record `SEOD-NNN` first, then `/build` to implement)
- Implementation tasks → `pm-github-workflow` (suggest, the user creates issues)
- Layout-affecting recommendations → `/design` (ux-behaviour) or `/build` (frontend-ts-expert)
