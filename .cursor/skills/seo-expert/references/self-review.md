# SEO Expert — Self-Review Lens

Loaded on demand at step 7 of the Facilitator Workflow.

---

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll skip the Google Search Central citation, this is well-known SEO." | "Well-known SEO" is full of outdated lore. Cite the doc or do not recommend it. |
| "I'll predict a 30% traffic increase to make the case." | Traffic predictions are not data. Frame as expected directional impact. |
| "I'll add `noindex` to fix the duplicate content." | `noindex` on the wrong page can de-list the entire section. Use canonicals or robots.txt with confirmation. |
| "The schema can stretch the truth a bit, Google won't notice." | Google does notice, and penalizes. Honest markup only. |
| "I'll skip the rollback plan, the change is small." | SEO changes that go wrong take weeks to recover. Always document rollback. |
| "I'll guess the keyword intent, it's probably informational." | Wrong intent = wrong content = wasted work. Ask or check Search Console. |
| "I'll fold the new audit into the existing one." | Audits are time-stamped. New scan = new audit. |
| "I'll edit the closed SEOD to add the missing rationale." | Edits destroy history. Write a superseding decision. |
| "I'll write 'this should improve rankings' without specifying which queries." | Vague impact = unmeasurable. Specify the query set or KPI. |
| "The user said 'optimize for AI search', I'll guess what that means." | "AI search" is contested terminology. Ask what they mean (Google AI Overviews? Generative SERPs? something else?). |
| "I'll recommend hreflang based on common patterns." | hreflang errors are the #1 international-SEO bug. Always reference Google's hreflang doc. |
| "Robots.txt is simple, I'll just add a Disallow." | Robots.txt mistakes can de-list entire sites. Always show the diff and ask. |

---

## Red Flags

### In audits

- Recommendations without Google Search Central citations
- Audit sections marked "passed" without supporting evidence
- A scope that is undefined or "the whole site"
- No risks or trade-offs section
- Recommendations with no priority order
- A canonical recommendation without explaining the duplicate-content cause
- A robots.txt change without an explicit diff

### In strategies

- KPIs that are not measurable
- Goals without a target query set
- No brand vs non-brand split
- No search intent classification
- Workstreams without owner or rough sequencing

### In decisions (SEOD-NNN)

- Only one option considered
- Options without `Risk level`
- An empty `Expected SEO impact` section
- An empty rollback plan
- No Search Console signals listed for measurement
- A "Decided" status without user confirmation

### In the agent's behavior

- The agent invents Google guidance without a citation
- The agent presents traffic predictions as facts
- The agent recommends a robots.txt or canonical change without showing the diff
- The agent recommends structured data that misrepresents page content
- The agent picks a strategy instead of presenting options
- The agent skips the Challenge step
- The agent edits a closed SEOD
- The agent invokes another skill directly

---

## Ask First — decision aids

| Situation | Ask First? | Why |
|---|---|---|
| Modifying robots.txt | **Yes** | Indexing-affecting; show the diff |
| Adding a canonical tag to a new page | **No** | "Always Do" — canonical hygiene |
| Changing canonical tag on an indexed page | **Yes** | Indexing-affecting |
| Recommending JSON-LD for a Product page (Google docs say "recommended") | **No** | Standard recommendation |
| Recommending JSON-LD with fields not in Google docs | **Yes** | Custom extension |
| Switching default schema format from JSON-LD to Microdata | **Yes** | Project-wide |
| Adding hreflang to a new multi-language section | **Yes** | High blast radius if wrong |
| Adding `meta description` to a page | **No** | Standard |
| Removing `meta description` from a page | **Yes** | Reduces snippet control |
| Adding a noindex tag to a page | **Yes** | De-listing risk |
| Removing a noindex tag from a page that should be indexed | **Yes** | Brings page back into the index — confirm intent |
| Adding sitemap entries for new pages | **No** | Standard |
| Removing pages from the sitemap | **Yes** | Reduces crawl signal |
| Recommending a URL structure migration | **Yes** | High-risk; SEOD required |
| Bumping priority on a low-impact recommendation | **Yes** | Reprioritization |
| Adding a Google Search Central citation to an existing recommendation | **No** | Improves the artifact |

### Default rule

If the change does not affect indexing, canonicalization, redirects, or robots.txt, and is grounded in a current Google Search Central doc, proceed (after presenting evidence). Otherwise, ask. **Indexing-affecting changes always require explicit user confirmation.**
