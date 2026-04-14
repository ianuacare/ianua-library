# COST-{NNN}: {Analysis Title}

**Date:** {YYYY-MM-DD}
**Author:** {name}
**Context:** {What infrastructure change or decision prompted this analysis}

---

## Current State

| Service | Resource | Configuration | Monthly cost |
|---|---|---|---|
| {Service} | {Resource name} | {Current config} | ${amount} |
| | | **Current total** | **${total}** |

## Proposed Options

### Option A: {Name}

| Service | Resource | Configuration | Monthly cost |
|---|---|---|---|
| {Service} | {Resource name} | {Proposed config} | ${amount} |
| | | **Option A total** | **${total}** |

**Change from current:** {+$X / -$X per month} ({+X% / -X%})

**Trade-offs:**
- {Performance impact}
- {Reliability impact}
- {Operational complexity}

### Option B: {Name}

| Service | Resource | Configuration | Monthly cost |
|---|---|---|---|
| {Service} | {Resource name} | {Proposed config} | ${amount} |
| | | **Option B total** | **${total}** |

**Change from current:** {+$X / -$X per month} ({+X% / -X%})

**Trade-offs:**
- {Performance impact}
- {Reliability impact}
- {Operational complexity}

## Cost Comparison

| | Current | Option A | Option B |
|---|---|---|---|
| Monthly cost | ${X} | ${Y} | ${Z} |
| Annual cost | ${X*12} | ${Y*12} | ${Z*12} |
| vs. current | — | {+/-$X/month} | {+/-$X/month} |
| vs. current % | — | {+/-X%} | {+/-X%} |

## Recommendation

**Recommended option:** {Option X}

**Rationale:** {Why this option provides the best balance of cost, performance, reliability, and operational complexity.}

## Implementation Plan

- [ ] {Step 1}
- [ ] {Step 2}
- [ ] {Step 3}

## Notes

- Prices based on {eu-west-1} region, {on-demand | reserved} pricing
- Data transfer costs {included | estimated separately}
- Prices as of {date} — verify current pricing before implementation

## Related

- Decision record: {INFRA-NNN}
- Architecture review: {ARCH-NNN}
