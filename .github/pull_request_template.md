# Summary

<!-- What changed and why. Link the issue: Closes #N -->

## Approach

<!-- How, and any decision a reviewer would otherwise have to reverse-engineer -->

## Evidence

<!-- Delete rows that don't apply. "Tests pass" alone is not evidence for
     capture or verdict changes — those need reconciliation numbers. -->

| Check | Result |
|---|---|
| `uv run pytest` | |
| `ruff check . && ruff format --check .` | |
| Reconciliation delta vs. authoritative source (§5.3, > 2% is a bug) | |
| Classifier gold-set agreement, if the taxonomy or prompt changed (§14, ≥ 80%) | |
| Ran against real local data without touching Claude Code | |

## Invariant checklist

Tick what applies; the ones in play for this diff must be affirmatively checked
(see `CLAUDE.md` → Project Invariants).

- [ ] **Nothing degrades Claude Code** — hooks are one-line `sh` (not Python),
      spool one file per invocation, `exit 0` unconditionally; no classification
      on the interactive path
- [ ] **The collector still does no interpretation** — no parsing, Pydantic or
      field extraction added under `collect/`; nothing there touches Ollama
- [ ] **`raw_event` stays append-only** — no enrichment writes over capture;
      labels keyed by `classifier_version`
- [ ] **No rejected-alternative creep** (TRD §1) — no ORM/Alembic/Postgres, no
      SPA/Streamlit/bundler, no LLM framework, no `cron`; DuckDB and
      `sqlite-vec` still behind their triggers
- [ ] **Classifier prompt restates the schema and enums** in the prompt text,
      not just `format=` (TRD §6)
- [ ] **One authoritative consumption source per provider** — others record a
      delta and contribute no tokens
- [ ] **No cross-pool summing** of allowance
- [ ] **Headroom is primary**; any dollar figure is labelled *notional list value*
- [ ] **No captured content committed** — no real transcripts, session ids, shell
      commands, absolute `/Users/...` paths, or credentials, in the diff **or in
      this description**
- [ ] **Parsing is defensive** — missing/unknown fields set `parse_degraded`
      rather than raising; `cc_version` recorded
- [ ] **No heavier infrastructure** — still SQLite, still no operated server,
      still no Anthropic-side gateway (§5.2)

## Phase 0 dependencies

<!-- Does this rest on an assumption Phase 0 was meant to settle? If so, link
     the finding in phase0/findings.md. If the finding doesn't exist yet, say so
     and explain why proceeding is safe anyway. -->

## Risk and rollback

<!-- What breaks if this is wrong, and how to back it out. Note that raw events
     are reconstructible from transcripts on disk — unless this PR changes the
     schema, in which case say how history survives. -->
