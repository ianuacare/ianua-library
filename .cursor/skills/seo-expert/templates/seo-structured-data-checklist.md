# Structured data — implementation checklist

| Field | Value |
|-------|-------|
| **Page / template** | {URL pattern or component} |
| **Date** | {YYYY-MM-DD} |
| **Owner** | {name/role} |
| **Schema format** | JSON-LD / Microdata / RDFa (prefer JSON-LD per project default) |

## 1. Page–markup alignment

- [ ] Markup describes **content users can see** on the page (no hidden or misleading fields)
- [ ] Primary entity matches the **main topic** of the page
- [ ] Required and recommended properties for the chosen type are satisfied **per current Google documentation**
- [ ] Images, dates, prices, ratings (if used) are **accurate and maintained**

## 2. Type selection

| Content type | Chosen schema.org type(s) | Eligible rich result (if any) | Doc link |
|--------------|---------------------------|---------------------------------|----------|
| | | | |

## 3. Implementation

- [ ] Single clear `@type` (or valid graph) per page where appropriate
- [ ] No conflicting duplicate types for the same visible entity
- [ ] IDs / URLs are absolute and stable where required
- [ ] Breadcrumb / sitelinks markup matches visible navigation (if used)

## 4. Validation

- [ ] **Rich Results Test** (or Search Console enhancement reports) run on representative URLs
- [ ] No errors; warnings reviewed and accepted or fixed
- [ ] Sampled pages after deploy match staging validation

## 5. Monitoring

- [ ] Search Console property covers the URL set
- [ ] Owner knows where to check structured data **errors** after releases
- [ ] Plan for content/CMS changes that affect markup fields

## Notes

{Edge cases, CMS fields, localization, A/B tests affecting content.}

## References

- Google Search Central structured data docs: {URLs}
- Related audit: {SEO-NNN}
- Related decision: {SEOD-NNN}
