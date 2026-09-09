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

**Week one — before committing to the build.** Nothing is built yet. Two
experiments come first, and either can invalidate weeks of work: **W1**, a
throwaway spike over existing transcript history to find whether the
over-provisioning finding exists at all, and **W2**, hand-testing the one tier
cell the headline number rests on. Phase 0 follows; Phase 1 follows that.

- [`src-documents/milestones.md`](src-documents/milestones.md) — what to do next: unknowns, milestones, standing risks
- [`src-documents/prd.md`](src-documents/prd.md) — product spec: problem, taxonomy, verdict rules, phases
- [`src-documents/trd.md`](src-documents/trd.md) — technical design: language, topology, storage, scheduling
- [`phase0/findings.md`](phase0/findings.md) — the six questions that block Phase 1

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
