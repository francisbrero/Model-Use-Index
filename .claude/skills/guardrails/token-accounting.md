# Guardrail — counting tokens and money

**Enforcement: warn.** Fires on any code that reads `message.usage`, sums
tokens, prices anything, or attributes spend to a session, routine or model —
`normalize/`, `enrich/allowance.py`, `analyses/`, and every ad-hoc script.

## The invariant

**Every token is counted exactly once, from one authoritative source, and every
dollar figure is labelled *notional list value*** (`CLAUDE.md` invariants 3, 5
and 10; PRD §2.1, §5.3).

This guardrail exists because the naive reading of a transcript is wrong by
roughly **2×**, and wrong in a way that looks perfectly healthy. W1 (2026-09-09)
published a $43,683 figure before catching it. The real number was $23,059.

## 1. Deduplicate before any arithmetic

**Claude Code writes one assistant JSONL record per content block.** A turn with
text plus two `tool_use` blocks becomes three records, and each repeats *the
same* `usage` object. The records have distinct `uuid`s, distinct positions in
the file, and nothing malformed about them.

Measured on this operator's history:

| | |
|---|---|
| Opus assistant records | 72,083 |
| Unique API responses | 37,769 |
| Duplicates | **34,314 (48%)** |
| Naive sum | $43,972 |
| Correct | **$23,059** |
| Overstatement | **91%** |

```python
# dedup key -- NOT uuid, NOT the record
key = (rec["message"]["id"], rec.get("requestId"))
```

**Take the max per field across the group.** Within a duplicate group
`output_tokens` can differ: a partial streaming snapshot is written first and
the final count later (5,951 groups here). So:

- `first-seen` **undercounts output** — the trap one level below the obvious one.
- `last-by-file-order` is not reliable either.
- `max` per field is correct for all four fields; cache fields are constant
  within a group.

Publicly documented, so treat it as a known property rather than a local quirk:
[ccusage #888](https://github.com/ryoppippi/ccusage/issues/888),
[claude-code #5034](https://github.com/anthropics/claude-code/issues/5034),
[claude-devtools #74](https://github.com/matt1398/claude-devtools/issues/74),
[claude-code #27361](https://github.com/anthropics/claude-code/issues/27361).
One reports 51–55% of entries as duplicates.

**Where it goes.** `normalize/`, never `collect/` — the collector stays
uninterpreted (invariant 2) and the duplicate records stay in `raw_event`
untouched (invariant 2b). Dedup is a *derivation*, so it must be reproducible
from raw events.

**Wire the ratio to `mui doctor`.** A sudden move in the duplicate ratio means
the transcript writer changed — invariant 7's schema-drift canary wearing a
different hat.

## 2. Price the four fields separately

Cache traffic is the majority of spend, not a rounding detail. On this history
it is **93% of Opus notional value** (57.9% cache read, 34.8% cache write)
against 7.2% output. A model that prices only `input_tokens` and `output_tokens`
misses almost all of it.

| Field | Rate relative to input |
|---|---|
| `input_tokens` | 1× |
| `output_tokens` | 5× |
| `cache_creation_input_tokens` | 1.25× |
| `cache_read_input_tokens` | 0.1× |

Rates live in the **versioned model registry**, never inline in an analysis.
`cache_read` at the input rate is a 10× error on the largest line item.

## 3. Never sum across allowance pools

Anthropic and OpenAI/Codex are separate ceilings (invariant 4). Always group by
`allowance_pool`. A combined total is not a smaller finding — it is a
meaningless number that hides the pool-balance question (A6).

## 4. Headroom is the unit; dollars are for ranking only

We are on seat subscriptions, not metered billing (invariant 5). `allowance_pct`
is primary. **Every dollar figure carries the words *notional list value*** — in
code, in output, in the UI, in a PR body, in a Slack message. No exceptions, and
no "obviously it's notional here".

## 5. `attributionSkill` identifies routines; it cannot cost them

The field tags a **contiguous run** of turns — the invocation itself — then
stops, while the work the routine drives continues untagged and carries most of
the cost. Observed tag ranges: turns 642–652, 384–442, 631–695, in sessions of
822, 563 and 980 turns.

Grouping spend by the field undercounts by an order of magnitude
(`/release-prod`: a fraction of its real $1,511). Use the tag as an **anchor**
and attribute forward to the end of its arc. **How to bound that arc is an open
Phase 0 question** — if you need it now, state the bound you chose and why.

## 6. Sidechain turns bill to the parent session

`isSidechain` turns appear inside the parent session's transcript — up to 2,102
in one session here — and a separate `subagents` pseudo-project holds its own
records. Decide explicitly whether a query counts subagent spend inside the
parent, alongside it, or both, and **never let a total include it twice.**

## Before you publish a number

```bash
# 1. dedup ratio -- if unique == records, you have not deduplicated
# 2. does the total move when you switch first-seen -> max? it should
# 3. is every $ figure within three words of "notional list value"?
grep -rn '\$' src/mui/ | grep -viE 'notional|list value|^\s*#' | head
```

Three questions for any figure leaving the machine:

1. **Deduplicated?** By `(message.id, requestId)`, max per field.
2. **Reproducible?** From `raw_event` plus the versioned registry alone
   (invariant 2b) — an unreproducible number is not a finding.
3. **Labelled?** *Notional list value*, and an upper bound labelled as one (R2).

A number that fails any of the three is worse than no number, because it will be
believed. That is the failure mode this whole guardrail is defending against.
