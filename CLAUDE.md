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

Three documents, deliberately split — do not resolve a question from the wrong
one. Each is markdown and is the only copy — **never generate a rendered `.html`
alongside one.** A second copy costs far more context, can't be diffed in review,
and goes stale the moment the markdown moves.

| Document | Owns | Cite as |
|---|---|---|
| [`src-documents/prd.md`](src-documents/prd.md) | The problem, taxonomy, verdict rules, delivery phases, success criteria | PRD §N |
| [`src-documents/trd.md`](src-documents/trd.md) | Language, process topology, storage, scheduling, packaging — and the reasoning per decision | TD §N |
| [`src-documents/milestones.md`](src-documents/milestones.md) | What to do next, in what order. Unknowns `U1`–`U9`, milestones `M0`–`M5`, standing risks `R1`–`R5` | MS §N / U-N / M-N / R-N |

The PRD/TD split exists so product requirements outlive stack choices. If Ollama
is replaced or the dashboard rebuilt, that must not reopen the argument about
what the tool is for. **So: a "what should this measure / how is it judged"
question is answered from the PRD; a "how is it built" question from the TD.**
Where the TD is more specific about implementation than the PRD, the TD wins.

The TD titles itself *Three Processes and a Database*; it cites itself as **TD**,
so use that in code comments and PR bodies rather than "TRD".

**TD §1 is a decision register** — 17 rows, each with the alternative that was
rejected and why. Read that table before proposing any stack change; most
"improvements" an agent would suggest are already in it as the rejected column.

**`milestones.md` is a working register, updated in place — not a rewrite
target.** Its §5 answer log is append-only. When an unknown gets resolved, fill
the answer inline and append a dated row; don't restructure the document.

**Status: M1 is merged (2026-09-14). A working pipeline exists.**
`mui run` goes transcripts → dedup → work units → signals → verdicts →
Datasette over the real corpus, read-only. **`milestones.md` §3/§6 is the live
sequencing authority — read it before starting any work, and if an issue
disagrees with it, the register wins.**

**Next: M2′, the gold set.** It is the critical path, because three separate
findings all resolve there and nowhere else (MS §3 M2′). **M1′ (live capture —
hooks, `launchd`, tailer, OTel) is NOT urgent**: backfill already reads the
whole corpus on demand, so hooks buy freshness that nothing currently needs.
Don't let it jump the queue for being more fun to build.

**Answered so far.** W1 — go, with a **reframed headline**: over-provisioning is
real but it is *high-ceremony, low-reasoning orchestration on Opus*, not "trivial
sessions". It produced invariants 10 and 11. `U10` — the work-unit grain is
`u10-next-anchor-v1`. `U4` — `message.usage` is on **87,354/87,354** messages
(closed). `U3a` — past rate-limit hits **are** on disk. `U1` — **Codex rollout
logs carry four-field token counts**, but `total_token_usage` is *cumulative per
session*, so summing it across records double-counts far worse than invariant 10
does. `U3` — **split answer: the OpenAI pool's allowance is directly readable**
(`rate_limits.used_percent`, both windows); the Anthropic pool must still be
modelled. The pools are therefore asymmetric, and rendering them identically
would be the most misleading thing the dashboard could do. `U2`/#18 — **96.1% of
subagent notional value runs on frontier.**

**What M1 shipped, and the two things about it that matter most:**

- **Five of six acceptance figures reproduce.** `/release-prod` at $1,418
  against $1,447 ±5%, arc overlap 0, duplicate ratio 48.1%.
- **The sixth does not, and was not made to.** W1's score-0 share of 43.4%
  lands at **21.7%** in code. The thresholds were deliberately not moved. The
  *qualitative* finding survives exactly — the top score-0 units are still
  `create-pr`/`release-prod`, near-total `Bash` — so the headline stands and only
  its magnitude is in dispute. **This is standing risk R6 (#22): closing that gap
  by nudging a threshold would fabricate the headline, and it is a one-line edit
  that looks like progress.** Don't. M2′ adjudicates.

**Two grains, and only one carries cost.** `work_unit` is the arc grain and is
the sole cost-bearing table; `prompt_unit` is the grain W1's signals were
calibrated on and deliberately has **no dollar column** — two tables each summing
to the corpus is a 2× double-count waiting for an ad-hoc Datasette join.

**Every number the slice emits is labelled `notional list value` and
`provisional`, and no headroom figure is emitted at all** (a documented temporary
deviation from invariant 5, not a redefinition). `v_caveats` carries all eight
known gaps as rows rather than prose, because Datasette renders tables.

## Project Invariants

These are load-bearing. Violating one produces a class of confidently-wrong
change, so each is called out here rather than left to be rediscovered.

### 1. Never break the thing being observed

This tool observes Claude Code; it must never degrade it (§13 Failure isolation).

- **Hooks must not be Python** (TD §4). Interpreter startup is 50–100 ms, which
  would be a measurable tax on every tool call. A hook is a one-line `sh` script
  that spools its stdin payload and exits — roughly 1 ms, no interpreter, no
  network, no lock, no way to hang a session:

  ```sh
  #!/bin/sh
  exec cat > "$HOME/.model-use-index/spool/$(date +%s)-$$-$PPID.json"
  ```

- **Spool to a directory, one file per invocation — never a shared append-only
  file** (TD §4). Appends under `PIPE_BUF` to an `O_APPEND` file are atomic, but
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

TD §2.1 calls this the load-bearing decision, and it is the one most easily
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
  Ollama being absent entirely (TD §15).
- The `collect/` → `normalize/` → `enrich/` directory split *is* this boundary
  made physical (TD §12). Keep it visible; don't blur it.

### 2b. The raw event store is append-only

`raw_event` is never updated and never deleted (PRD §5). Enrichment never
overwrites capture. Re-derivation from raw events is the entire recovery story,
which is why retention favours keeping everything (TD §5.2: compress payloads
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

**Pydantic with `extra="ignore"` is the drift defence** (TD §3.1) — this is not
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

TD §6 flags this as "the failure mode that sinks a v1", so it gets its own rule.

**Ollama never shows the model the schema** — `format` only constrains sampling.
The schema and its enum values must *also* be restated in the prompt text.
Grammar constraint alone yields structurally perfect JSON containing semantic
nonsense, which is far harder to notice than a parse error. Classifier
concurrency is **1**; Ollama on 8 GB gains nothing from parallel requests and
will thrash.

### 8. Don't reach for heavier infrastructure

Deliberate constraints from PRD §6/§12 and the TD §1 decision register. An
agent "improving" any of these is making the project worse — each already has a
rejected alternative on the record:

- **SQLite**, WAL, `synchronous=NORMAL`, `busy_timeout=5000`, single file at
  `~/.model-use-index/store.db`. Not Postgres. A year of heavy use is a few
  hundred MB.
- **Raw SQL in `.sql` files. No ORM** (TD §5) — the schema is analytical and the
  queries are the product. Migrations are numbered `.sql` files applied against a
  `schema_version` table. **Not Alembic.**
- **FastAPI + Jinja + HTMX. No build step, no npm, no bundler** (TD §8).
  Explicitly rejected: React/any SPA, **Streamlit** (its rerun model would fight
  the approved mockups), Next.js. Charts are server-rendered inline SVG, with
  Observable Plot from a CDN only where hover or zoom genuinely earns it — not
  D3 directly.
- **Datasette is the Phase 1 UI** (TD §8.1). Don't hand-build a dashboard
  before Phase 3; point Datasette at the file and get a queryable, faceted UI
  plus the PRD's SQL console for zero code. Keep it afterwards for ad-hoc work.
- **No LLM framework.** `httpx` straight to Ollama's HTTP API (TD §6).
  LangChain/LlamaIndex are overhead for one structured call and obscure the one
  thing that matters — the exact prompt text.
- **Defer DuckDB and `sqlite-vec`.** Both have concrete adoption triggers, not
  vibes: DuckDB when a dashboard query exceeds ~300 ms (TD §5.1); `sqlite-vec`
  above roughly 1M vectors (TD §7). Below those they are dependencies buying
  nothing, and both are addable later without a migration.
- **`launchd`, not `cron`** (TD §9). cron never fires while a laptop is asleep
  and never catches up, so a 02:00 job on a machine that closes at 23:00 runs
  approximately never.
- No server anyone has to operate. `localhost` only, single operator.
- **No Anthropic-side gateway.** A decided "no" (PRD §5.2), not a deferral —
  ToS/subscription-auth uncertainty, silent prompt-cache defeat, and the risk
  landing on the workday rather than on the tool. Don't propose one.

### 8b. Standing risks — don't help them along

MS §4. These never resolve; they only get managed, and an agent optimising for
apparent progress will make three of them worse.

- **R1 — the gold-set day gets skipped.** A full day of tedious hand-labelling
  with no visible output. It will feel skippable every time. It's the difference
  between a report you act on and one you quietly second-guess. Never propose
  folding it into Phase 2 or "doing it later"; it's a named calendar day.
- **R2 — estimates over-promise and credibility rots.** Reclaimable headroom is
  **an upper bound by construction** — it assumes the cheaper model finishes in
  the same tokens, and it won't. Label it an upper bound *in the UI*, and at M5
  publish the gap between predicted and realised. A tool that shows its own
  prediction error stays trusted; one that quietly stops mentioning predictions
  does not.
- **R3 — silent ingestion failure.** Hence `mui doctor` as a first-class
  deliverable, and the data-quality view shipping **with** the first dashboard,
  not after it.
- **R4 — scope creep into a product.** The PRD §3 non-goals are load-bearing:
  internal tooling, one machine, one operator. Multi-user is a separate decision
  (4c), never a rollout. Don't add auth, don't add a server, don't generalise.
- **R5 — schema drift** is managed structurally by invariant 2, not procedurally.

### 9. The 8 GB memory budget is the binding design constraint

Apple Silicon, 8 GB unified memory (§4). After macOS, an IDE, a browser and
Claude Code, the realistic local-model budget is **~3 GB resident, 4 GB at a
stretch.** Classifier is `qwen3:4b` via Ollama, runs at 02:00 with the machine to
itself. Verify actual quantisation with `ollama show` before trusting a tag's
advertised size — tags are not uniformly Q4.

### 10. Deduplicate `usage` before any arithmetic

**Summing `message.usage` per JSONL record overstates cost by ~91%.** Measured
on this operator's history: $43,972 naive against $23,059 correct, with 34,314
of 72,083 Opus assistant records being duplicates (W1, 2026-09-09).

Claude Code writes **one assistant record per content block** — a turn with text
plus two `tool_use` blocks becomes three records — and each repeats *the same*
`usage` object. The records have distinct `uuid`s and are genuinely separate
lines, so nothing about them looks wrong.

- **Dedup key is `(message.id, requestId)`**, not `uuid` and not the record.
- **Take the max per field across the group.** Within a duplicate group,
  `output_tokens` may differ — a partial streaming snapshot is written first and
  the final count later (5,951 groups here). First-seen dedup *undercounts*
  output; last-by-file-order is not reliable either.
- Cache fields are constant within a group; `max` is safe for all four.
- This belongs in `normalize/`, never in `collect/` — invariant 2 still holds,
  and the raw duplicate records stay in `raw_event` untouched (invariant 2b).
- `mui doctor` should report the duplicate ratio. A sudden change means the
  transcript writer changed, which is invariant 7's canary in another guise.

Not a local quirk — it is publicly documented in
[ccusage #888](https://github.com/ryoppippi/ccusage/issues/888),
[claude-code #5034](https://github.com/anthropics/claude-code/issues/5034) and
[claude-devtools #74](https://github.com/matt1398/claude-devtools/issues/74),
one of which measures 51–55% of entries as duplicates. **Any tool that reports
Claude Code cost without this is wrong by roughly 2×**, which is the specific way
this project would lose credibility on its first published number.

The full accounting rules — dedup, per-field pricing, pool separation, anchor
attribution, sidechain double-counting, and the pre-publication checks — live in
the **`/token-accounting`** skill
([`.claude/skills/token-accounting/SKILL.md`](.claude/skills/token-accounting/SKILL.md)).
A `UserPromptSubmit` hook surfaces it whenever a prompt mentions cost, spend,
tokens or usage; invoke it directly with `/token-accounting`.

### 10b. Limit-hit records carry no tokens — and must not be filtered out

U3a, answered 2026-09-09. A rate-limit hit lands in the transcript as an
`assistant` record whose `message.model` is the literal string `<synthetic>`,
whose `usage` is **all zeros**, and which carries `error: "rate_limit"` plus
`apiErrorStatus: 429`. It is the only on-disk evidence of an allowance boundary.

- **Never drop zero-`usage` or `<synthetic>` assistant records in `collect/`.**
  A reasonable-looking "skip records with no tokens" filter deletes the entire
  allowance-calibration signal. Invariant 2 already forbids this kind of
  interpretation in the collect path; this is the concrete case.
- **Dedupe limit hits by stated reset target, not by record.** One limit event
  writes one record per *live* session — 29 records on disk are only **6
  episodes**. This is a *different* key from invariant 10's `(message.id,
  requestId)`; both rules apply, to different record classes.
- **Prefer `quotaLimits` over the display text.** Client `2.1.245`+ carries
  `{status, resetsAt (unix epoch), rateLimitType, …}`. Older clients carry the
  reset only as a UI string — local wall-clock, tz-named, no date on the 5-hour
  form. Parse text as fallback and record `version` on every row.
- **`error` is an enum, not a boolean.** `server_error` (28) is at parity with
  `rate_limit` (29); an error record is not a limit hit.
- Limit accounting is **per-pool, not per-session** — 3 of 29 hits are
  `isSidechain: true`, so subagents hit the ceiling too (invariant 4).

### 11. `attributionSkill` identifies routines; it cannot cost them

The field tags only a **contiguous run** of turns — the skill invocation itself —
then stops, while the work the routine drives continues untagged and carries most
of the cost. Grouping spend by the field undercounts by an order of magnitude.
Attribute from the tag as an **anchor** to the end of its arc. How to bound that
arc is an open Phase 0 question, not a solved one.

## Repository Layout

Current — M1 is built into the TD §12 shape:

```text
CLAUDE.md              # single source of truth
AGENTS.md -> CLAUDE.md # symlink (Codex CLI)
GEMINI.md -> CLAUDE.md # symlink (Gemini CLI)
src-documents/         # prd.md · trd.md · milestones.md · ui.html (mockups)
phase0/findings.md     # the six blocking questions (after W1/W2)
pyproject.toml         # uv, ruff, pytest
config.toml.example    # NOTE: signal thresholds are deliberately NOT here (R6)
datasette.yaml         # Datasette metadata — puts the readable views first
migrations/            # 001_init · 002_model_registry_seed · 003_views
                       # · 004_readable_views
src/mui/
  db.py                # connection + migration runner (no ORM, no Alembic)
  cli.py               # typer
  verdict.py           # pure functions — keep it that way (TD §11)
  collect/transcript.py    # parses NOTHING beyond a session id (invariant 2)
  normalize/           # work_unit.py pricing.py tools.py pipeline.py
  enrich/              # signals.py classify.py pipeline.py
  verify.py            # the acceptance gate
tests/                 # 315 tests · fixtures/anchor_shapes (scrubbed, synthetic)
```

Not built yet, and each deliberately deferred: `hooks/`, `launchd/`,
`wrappers/codex`, `src/mui/web/`, `src/mui/analyses/`, `enrich/allowance.py`,
`normalize/reconcile.py`, `normalize/delegation.py`, `collect/otel.py`,
`collect/hooks.py`, `collect/codex.py`.

Client-side configuration (hook registrations, plists, the wrapper) stays in
**one place**. The eventual multi-user phase would package this half as a Claude
Code plugin, and scattering it now means untangling it later (TD §16).

## Architecture — three processes, not one daemon

TD §2. The components have incompatible resource and failure profiles, so they
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
next wake (TD §9).

## Development

M1 is built (#14, merged 2026-09-14). `uv run mui run` executes the whole
pipeline; `uv run mui verify` is the acceptance gate and **exits non-zero if any
asserted figure stops reproducing** — run it after touching anything in
`normalize/` or `enrich/`. `uv run mui open` starts Datasette with the metadata
that puts the readable views first.

Remaining Phase 1 work follows TD §14, sequenced so something is checkable at
every step rather than integrating at the end.

Stack: Python 3.12+ with `uv`, `ruff` (lint + format), `pytest`. `mui` is a
`typer` CLI and the front door. Built: `mui status` (now prints the
per-pool summary), `mui backfill`, `mui normalize`, `mui classify`, `mui run`,
`mui verify`, `mui open`. Planned: `mui doctor`, `mui reclassify --since`.

**`mui doctor` is a first-class deliverable, not a nice-to-have** (TD §13). This
runs unattended, and a tool that stopped ingesting three weeks ago while still
rendering a confident dashboard is worse than no tool. It checks: last event per
source against a staleness threshold, `raw_event` → `work_unit` watermark lag,
Pydantic validation-failure rate, reconciliation delta per provider, orphaned
delegations, classifier queue depth and last successful batch, allowance-model
fit, free disk and DB size. Same numbers back the dashboard's data-quality view.

### Testing

Two kinds carry almost all the value (TD §11):

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
- `src-documents/trd.md` is ~470 lines. Grep for the `## N.` heading and read
  that section.
- **Never read `src-documents/ui.html`.** It's the approved dashboard mockups and
  the only HTML left in the repo — hand-authored, not a render. Open it in a
  browser; reading the markup costs thousands of lines of styling to learn what a
  screenshot would tell you.

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
