# Model Use Index

A local-first observability and right-sizing system for Claude Code usage.

It captures what Claude Code — and the Codex subagents it delegates to — actually
consumed, classifies each unit of work with a local model, and produces a
per-pool allowance report with an over/under-provisioning verdict attached.

The point is not to reduce an invoice. We are on seat subscriptions, so the
scarce resource is **frontier-model headroom**: the reason someone gets
rate-limited on Thursday afternoon. This report says which low-complexity work
ate it.

## Status

**M1 has shipped** — the first end-to-end slice runs: backfill → dedup → work
units → a crude classifier → verdicts → Datasette. Week one is closed. **W1**
(the throwaway spike over existing transcript history) answered *go*, with a
reframed headline: the over-provisioning is high-ceremony, low-reasoning
orchestration on Opus, not trivial sessions. **W2** was closed *moot* after a
two-run pilot, and **U10** pinned the work-unit grain.

Two constraints on the slice, and neither is a temporary embarrassment to be
quietly dropped: it emits **no headroom figure** (the allowance questions are
deferred), and every classification is **labelled provisional** until the gold
set clears.

- [`src-documents/milestones.md`](src-documents/milestones.md) — the live register: unknowns, milestones, standing risks, and the append-only answer log
- [`src-documents/prd.md`](src-documents/prd.md) — product spec: problem, taxonomy, verdict rules, phases
- [`src-documents/trd.md`](src-documents/trd.md) — technical design: language, topology, storage, scheduling
- [`phase0/findings.md`](phase0/findings.md) — the Phase 0 questions, and which of them are still open

## About the numbers

Every dollar figure in this repository — in the documents, the dashboard
mockups, and the code comments — is **notional list value**: what the tokens
would have cost at published per-token list rates. We are on seat
subscriptions, so none of it was ever invoiced. It is a ranking device, not a
bill.

Absolute figures in the **shipped artifacts** — the dashboard mockups, the
code, the SQL — are rounded to obviously illustrative values. They indicate
scale, not exact spend. The design documents under `src-documents/` keep their
original figures as the historical record of how each decision was reached, so
precision there is deliberate rather than an oversight.

**The ratios are the load-bearing claim**, and they are unedited:

| | |
|---|---|
| **~91%** | how much summing `message.usage` per JSONL record overstates cost, before deduplication — any tool that skips this is wrong by roughly 2× |
| **43.4%** | share of frontier-model value on the main project that carries no complexity signal at all |
| **73.4%** | share of all frontier value in that one project and its worktrees |
| **8.9%** | share of that project's frontier value sitting in a single `/release-prod` routine |
| **7.1%** | of that project's frontier value that same routine could release if downgraded — an **upper bound**, not a forecast (see below) |

Reclaimable headroom, wherever it appears, is **an upper bound by
construction**: it assumes a cheaper model finishes the same work in the same
tokens, and it will not.

## Design in one paragraph

Four decoupled planes: **capture** (transcript tailer, native OTel export,
targeted hooks, delegated-agent logs) → **normalise** (reconcile sources into a
canonical `work_unit`, join delegated calls to their parent) → **enrich**
(nightly local classifier, outcome-signal extractor, allowance model, verdict
rules) → **serve** (SQLite, a localhost dashboard, and a raw SQL console).
Raw capture is append-only and never overwritten by enrichment, so when the
taxonomy changes we re-run over history instead of losing it.

Three processes coordinated only through SQLite and the filesystem —
`mui-collect` always on, `mui-batch` at 02:00, `mui-web` on demand. The
collector deliberately does no parsing, so a Claude Code schema change can
degrade the tool but cannot break capture. Python + `uv`, SQLite + raw SQL,
FastAPI + Jinja + HTMX, Ollama via `httpx`, scheduled by `launchd`.

Runs entirely on one laptop. No prompt content leaves the machine. Nothing in it
may ever break Claude Code.

## Working in this repo

Read [`CLAUDE.md`](CLAUDE.md) first — it carries the project invariants that
turn the PRD's design decisions into rules an agent (or a human) can follow.
