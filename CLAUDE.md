# CLAUDE.md

This file provides guidance to AI coding assistants working in this repository.
It is the single source of truth: `AGENTS.md` (Codex) and `GEMINI.md` (Gemini CLI)
are symlinks to this file, so edit only this one.

## Repository Purpose

**Model Use Index** — a local-first observability and right-sizing system for
Claude Code usage. It captures what Claude Code (and delegated Codex subagents)
actually consumed, classifies each unit of work with a local model, and produces
a per-pool allowance report with an over/under-provisioning verdict.

## Which Document Owns What

Two specs, deliberately split — do not resolve a question from the wrong one:

| Document | Owns | Cite as |
|---|---|---|
| [`src-documents/prd.md`](src-documents/prd.md) | The problem, taxonomy, verdict rules, delivery phases, success criteria | PRD §N |
| [`src-documents/trd.html`](src-documents/trd.html) | Language, process topology, storage, scheduling, packaging — and the reasoning per decision | TRD §N |

The split exists so product requirements outlive stack choices. If Ollama is
replaced or the dashboard rebuilt, that must not reopen the argument about what
the tool is for. **So: a "what should this measure / how is it judged" question
is answered from the PRD; a "how is it built" question from the TRD.** Where the
TRD is more specific about implementation than the PRD, the TRD wins — it was
written later and its §1 decision register is the current answer.

The TRD is HTML-only (no `.md` sibling). To read a section without burning
context on markup, extract it to text first rather than reading the raw file.

**TRD §1 is a decision register** — 17 rows, each with the alternative that was
rejected and why. Read that table before proposing any stack change; most
"improvements" an agent would suggest are already in it as the rejected column.

**Status:** Phase 0 (reconnaissance). Nothing is built yet. Phase 0 is pure
investigation whose purpose is to replace six assumptions with facts (§14). Do
not build Phases 1–3 machinery on assumptions Phase 0 has not yet settled.

## Project Invariants

These are load-bearing. Violating one produces a class of confidently-wrong
change, so each is called out here rather than left to be rediscovered.

### 1. Never break the thing being observed

This tool observes Claude Code; it must never degrade it (§13 Failure isolation).

- **Hooks must not be Python** (TRD §4). Interpreter startup is 50–100 ms, which
  would be a measurable tax on every tool call. A hook is a one-line `sh` script
  that spools its stdin payload and exits — roughly 1 ms, no interpreter, no
  network, no lock, no way to hang a session:

  ```sh
  #!/bin/sh
  exec cat > "$HOME/.model-use-index/spool/$(date +%s)-$$-$PPID.json"
  ```

- **Spool to a directory, one file per invocation — never a shared append-only
  file** (TRD §4). Appends under `PIPE_BUF` to an `O_APPEND` file are atomic, but
  hook payloads can exceed it and interleaved writes would corrupt records
  *invisibly* — the worst failure mode available. One file per invocation costs
  nothing and cannot interleave.
- **Hooks `exit 0` unconditionally and stay non-blocking.** A hook that returns
  non-zero can wedge a turn.
- Every component fails *safe*: classifier down → rows stay unclassified;
  tailer down → transcripts are still on disk and backfill later.
- **Zero added latency to interactive turns** is a hard constraint, not a target.
  This is why classification is a nightly batch job and never inline.

### 2. The collector does no interpretation

TRD §2.1 calls this the load-bearing decision, and it is the one most easily
eroded by a well-meaning edit.

`mui-collect` extracts *only* enough to get a `session_id` and a content hash,
appends the raw payload, and moves on. **It therefore cannot be broken by a
schema change, because it does not understand the schema.** All parsing lives in
`mui-batch`, where a failure is recoverable by fixing the parser and re-running
over `raw_event`.

- **Never add parsing, validation, or field extraction to the collect path.** A
  Pydantic model in `collect/` is the specific mistake this invariant exists to
  prevent — it turns a structural guarantee back into an aspiration.
- Nothing in the collect path may touch Ollama. `mui-collect` must survive
  Ollama being absent entirely (TRD §15).
- The `collect/` → `normalize/` → `enrich/` directory split *is* this boundary
  made physical (TRD §12). Keep it visible; don't blur it.

### 2b. The raw event store is append-only

`raw_event` is never updated and never deleted (PRD §5). Enrichment never
overwrites capture. Re-derivation from raw events is the entire recovery story,
which is why retention favours keeping everything (TRD §5.2: compress payloads
older than 90 days in place; don't delete them).

- Classification labels live in a **separate table** keyed by `work_unit_id` +
  `classifier_version`. The taxonomy *will* change; when it does we re-run
  enrichment over history rather than losing it.
- Every derived number must be reproducible from raw events plus the versioned
  model registry, allowance model, taxonomy, and rules config (§13).

### 3. Consumption has exactly one authoritative source per provider

OTel for Anthropic; the agent's own logs for delegated providers (§5.3).

- Other sources record a `reconciliation_delta` but **never contribute tokens.**
  Three sources with different clocks is precisely how double-counting happens.
- Text content always comes from the transcript (Source A), or Source E1 for
  delegated work.
- A persistent reconciliation delta above 2% is a bug, not rounding.

### 4. Allowance pools never sum

Anthropic allowance and OpenAI/Codex allowance are separate ceilings (§2.1).
Summing them produces a meaningless number and hides the single most important
finding (the pool-balance question, A6). Always group by `allowance_pool`.

### 5. Headroom is the unit of account, not dollars

We are on seat subscriptions, not metered billing (§2.1). The primary measure is
`allowance_pct` — share of a pool's period allowance consumed. A dollar figure is
computed for ranking only and must be labelled **notional list value** every
single place it appears in code, output, or UI.

### 6. Privacy — no prompt content leaves the machine

G4, and §13 Privacy.

- Excerpts strip full bash commands (verbs only: `pytest`, `git`, `npm`) and
  full file paths.
- This tool emits no telemetry about itself.
- Telemetry env vars (`CLAUDE_CODE_ENABLE_TELEMETRY`, `OTEL_*`) belong in the
  operator's **shell profile, outside any repo** — there is a documented
  exfiltration technique where a hostile repo's checked-in settings point
  telemetry headers at an attacker-controlled command. The OTLP endpoint binds
  to `127.0.0.1` only.
- Never commit a real transcript, session record, or `store.db`. See
  `.gitignore`; sample fixtures must be hand-scrubbed and obviously synthetic.

### 7. The transcript schema is unstable — parse defensively

`~/.claude/projects/**/*.jsonl` is internal and undocumented; Anthropic advises
against depending on it (§5.1 Source A).

**Pydantic with `extra="ignore"` is the drift defence** (TRD §3.1) — this is not
a style preference, it's the mitigation:

- Unknown fields are dropped without error.
- Missing fields raise a **countable `ValidationError`**, not a `KeyError` three
  layers down.
- **The count of validation failures is the schema-drift canary.** Wire it to
  `mui doctor`; alert if records failing to yield token counts cross 1%.
- Record the Claude Code `version` on every record so drift bisects to a release.
- The same Pydantic models generate the classifier's JSON schema, so the taxonomy
  has **one** definition rather than two that quietly diverge.

### 7b. Restate the schema in the classifier prompt

TRD §6 flags this as "the failure mode that sinks a v1", so it gets its own rule.

**Ollama never shows the model the schema** — `format` only constrains sampling.
The schema and its enum values must *also* be restated in the prompt text.
Grammar constraint alone yields structurally perfect JSON containing semantic
nonsense, which is far harder to notice than a parse error. Classifier
concurrency is **1**; Ollama on 8 GB gains nothing from parallel requests and
will thrash.

### 8. Don't reach for heavier infrastructure

Deliberate constraints from PRD §6/§12 and the TRD §1 decision register. An
agent "improving" any of these is making the project worse — each already has a
rejected alternative on the record:

- **SQLite**, WAL, `synchronous=NORMAL`, `busy_timeout=5000`, single file at
  `~/.model-use-index/store.db`. Not Postgres. A year of heavy use is a few
  hundred MB.
- **Raw SQL in `.sql` files. No ORM** (TRD §5) — the schema is analytical and the
  queries are the product. Migrations are numbered `.sql` files applied against a
  `schema_version` table. **Not Alembic.**
- **FastAPI + Jinja + HTMX. No build step, no npm, no bundler** (TRD §8).
  Explicitly rejected: React/any SPA, **Streamlit** (its rerun model would fight
  the approved mockups), Next.js. Charts are server-rendered inline SVG, with
  Observable Plot from a CDN only where hover or zoom genuinely earns it — not
  D3 directly.
- **Datasette is the Phase 1 UI** (TRD §8.1). Don't hand-build a dashboard
  before Phase 3; point Datasette at the file and get a queryable, faceted UI
  plus the PRD's SQL console for zero code. Keep it afterwards for ad-hoc work.
- **No LLM framework.** `httpx` straight to Ollama's HTTP API (TRD §6).
  LangChain/LlamaIndex are overhead for one structured call and obscure the one
  thing that matters — the exact prompt text.
- **Defer DuckDB and `sqlite-vec`.** Both have concrete adoption triggers, not
  vibes: DuckDB when a dashboard query exceeds ~300 ms (TRD §5.1); `sqlite-vec`
  above roughly 1M vectors (TRD §7). Below those they are dependencies buying
  nothing, and both are addable later without a migration.
- **`launchd`, not `cron`** (TRD §9). cron never fires while a laptop is asleep
  and never catches up, so a 02:00 job on a machine that closes at 23:00 runs
  approximately never.
- No server anyone has to operate. `localhost` only, single operator.
- **No Anthropic-side gateway.** A decided "no" (PRD §5.2), not a deferral —
  ToS/subscription-auth uncertainty, silent prompt-cache defeat, and the risk
  landing on the workday rather than on the tool. Don't propose one.

### 9. The 8 GB memory budget is the binding design constraint

Apple Silicon, 8 GB unified memory (§4). After macOS, an IDE, a browser and
Claude Code, the realistic local-model budget is **~3 GB resident, 4 GB at a
stretch.** Classifier is `qwen3:4b` via Ollama, runs at 02:00 with the machine to
itself. Verify actual quantisation with `ollama show` before trusting a tag's
advertised size — tags are not uniformly Q4.

## Repository Layout

Current:

```text
CLAUDE.md              # single source of truth
AGENTS.md -> CLAUDE.md # symlink (Codex CLI)
GEMINI.md -> CLAUDE.md # symlink (Gemini CLI)
src-documents/         # prd.md (product) + trd.html (technical)
phase0/findings.md     # the six blocking questions
.claude/               # settings.json, agents/, commands/, skills/guardrails/
```

Target for Phase 1 (TRD §12) — build into this shape, don't invent another:

```text
pyproject.toml         # uv, ruff, pytest
config.toml.example
migrations/            # 001_init.sql, 002_allowance.sql, …
launchd/               # two .plist templates
hooks/spool.sh         # TRD §4 — one-line sh, not Python
wrappers/codex         # PRD §5.1 E2 — call-site attribution
src/mui/
  models.py            # Pydantic — one definition of every record
  collect/             # transcript.py otel.py hooks.py codex.py
  normalize/           # work_unit.py reconcile.py delegation.py
  enrich/              # excerpt.py classify.py signals.py allowance.py
  verdict.py           # pure functions
  analyses/            # a1_over.py a2_under.py a3_cluster.py …
  web/                 # FastAPI + Jinja + HTMX
  cli.py               # typer
tests/fixtures/        # golden records from Phase 0
```

Client-side configuration (hook registrations, plists, the wrapper) stays in
**one place**. The eventual multi-user phase would package this half as a Claude
Code plugin, and scattering it now means untangling it later (TRD §16).

## Architecture — three processes, not one daemon

TRD §2. The components have incompatible resource and failure profiles, so they
don't share a process:

| Process | Lifetime | Does |
|---|---|---|
| `mui-collect` | always on (`launchd KeepAlive`) | transcript + Codex watchers, hook-spool drain, OTLP receiver on `127.0.0.1:4318`. Writes **only** `raw_event` |
| `mui-batch` | 02:00 + light hourly pass | normalise → enrich → verdicts, as ordered phases |
| `mui-web` | on demand (`mui open`) | FastAPI, dies when idle |

Coordinated only through SQLite and the filesystem — **no message bus, no queue,
no supervisor beyond `launchd`.** Normalise and enrich are collapsed into one
scheduled process deliberately: it caps the system at **two writers**, so
SQLite's single-writer model is a non-issue rather than a source of intermittent
`database is locked` errors that appear only under load and only at night.

Don't run the enrichment batch on battery — check for AC power and defer to the
next wake (TRD §9).

## Development

Nothing is built yet. Phase 1's build order is TRD §14 — eight steps, each with
its own verification, sequenced so something is checkable at every step instead
of integrating everything at the end. **Datasette lands at step 4, early on
purpose**, because being able to look at real data before any enrichment exists
is what catches capture bugs while they're still cheap.

Stack: Python 3.12+ with `uv`, `ruff` (lint + format), `pytest`. `mui` is a
`typer` CLI and the front door: `mui status`, `mui backfill`,
`mui reclassify --since`, `mui doctor`, `mui open`.

**`mui doctor` is a first-class deliverable, not a nice-to-have** (TRD §13). This
runs unattended, and a tool that stopped ingesting three weeks ago while still
rendering a confident dashboard is worse than no tool. It checks: last event per
source against a staleness threshold, `raw_event` → `work_unit` watermark lag,
Pydantic validation-failure rate, reconciliation delta per provider, orphaned
delegations, classifier queue depth and last successful batch, allowance-model
fit, free disk and DB size. Same numbers back the dashboard's data-quality view.

### Testing

Two kinds carry almost all the value (TRD §11):

- **Golden-file parser tests.** Real transcript/OTel/hook/Codex records as
  fixtures; assert the normaliser's output. This is the regression suite for
  schema drift — the thing most likely to break — and Phase 0 collects the
  samples anyway. Fixtures must be scrubbed (invariant 6).
- **Pure-function tests on the verdict engine.** The rules are deterministic and
  side-effect free, which is why all 28 reference-report rows could be verified
  before the system existed. Keep `verdict.py` pure so this stays true.

Deliberately *not* worth much here: mocking Ollama, end-to-end browser tests,
coverage targets. Don't add them.

## Search Delegation

The dominant cost of a long session is cache-read at Opus rates. Accordingly:

- **Targeted lookups stay in the main context.** If you know the file path or
  symbol, use `Read` or `Bash grep` directly.
- **Open-ended exploration goes to an `Explore` subagent on Haiku** ("where does
  X live", "find callers of Y"). Use `sonnet` only when the search needs
  reasoning about the matches. Don't grep broadly in the main session.
- `src-documents/prd.md` is ~1200 lines. Read the section you need with
  `sed -n` or grep for the heading rather than reading the whole file.
- `src-documents/trd.html` is HTML with no `.md` sibling. Strip the markup to
  text once, then read the section — don't pull raw HTML into context:

  ```bash
  python3 -c "
  import re,html,sys
  s=open('src-documents/trd.html').read()
  s=re.sub(r'(?is)<(script|style|head)[^>]*>.*?</\1>',' ',s)
  s=re.sub(r'(?is)</(p|div|h[1-6]|li|tr)>','\n',s)
  s=re.sub(r'(?s)<[^>]+>',' ',s)
  print(re.sub(r'\n\s*\n+','\n',html.unescape(s)))" > /tmp/trd.txt
  ```

## PR Creation

When creating pull requests, ALWAYS read `.github/pull_request_template.md` and
reproduce its sections in the `--body` argument. Do not rely on GitHub
auto-filling the template — `gh pr create --body` overrides it.

## Git Workflow

Always use feature branches and PRs for changes:

1. Create a branch: `git checkout -b feature/description`
2. Make commits on the branch
3. Push and create PR: `gh pr create`
4. Wait for approval before merging
5. Never push directly to `master`

## Adding Instruction Files

If you add an instruction file for another assistant, **symlink it to
`CLAUDE.md`** rather than copying. Duplicated instruction files drift.
