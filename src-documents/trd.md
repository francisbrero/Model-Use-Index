# Three Processes and a Database

**Technical design and stack decisions for the Model Use Index**

| | |
|---|---|
| **Owner** | Francis Brero |
| **Status** | Draft v0.1 — decisions proposed, nothing built |
| **Date** | 9 September 2026 |
| **Companion** | *Model Use Index* (PRD). That document says **what** and **why**; this one says **how**. |
| **Scope** | Single operator, macOS, Apple Silicon, 8 GB unified memory |

---

## 0. How to read this

The PRD owns the problem, the taxonomy, the verdict rules and the delivery
phases. It should stay readable by someone who will never open the codebase.
This document owns everything below that line: language, process topology,
storage, scheduling, packaging, and the reasoning behind each.

Splitting them matters for a specific reason. **Product requirements should
outlive stack choices.** If Ollama is replaced, or the dashboard is rebuilt, or
Python turns out to be the wrong call, none of that should require reopening the
argument about what the tool is for. Section §8 of the PRD — the verdict engine —
is the part with the longest half-life, and it should not sit in the same
document as a recommendation about which web framework to use.

Everything here is chosen against one unusual constraint: **most of this will be
written by Claude Code, reviewed by one person, and then left to run unattended
on a laptop.** That makes *boring, legible, and loud when broken* worth more than
raw capability. Silent failure is the enemy throughout.

---

## 1. Decision register

The whole argument in one table. Each row is expanded below.

| # | Decision | Choice | Main alternative | Why this one |
|---|---|---|---|---|
| 1 | Language | **Python 3.12+, `uv`** | TypeScript / Node | Enrichment plane is Python-native; TS would shell out to Python anyway |
| 2 | Record schemas | **Pydantic** | dataclasses, raw dicts | `extra="ignore"` *is* the drift defence; also generates the classifier schema; validation-failure count *is* the canary |
| 3 | Process topology | **3 processes over SQLite** | one daemon; queue + workers | Incompatible resource profiles; caps the system at two writers |
| 4 | Capture / interpret split | **Collector writes raw only** | parse on ingest | A collector that doesn't understand the schema cannot be broken by a schema change |
| 5 | Hook implementation | **One-line `sh` → spool dir** | Python hook; shared append file | ~1 ms vs 50–100 ms; `PIPE_BUF` interleaving corrupts silently |
| 6 | Store | **SQLite + raw SQL** | Postgres; an ORM | No daemon; the queries *are* the product |
| 7 | Analytics engine | **Defer DuckDB** | adopt now | Concrete trigger instead: any dashboard query > 300 ms |
| 8 | LLM call | **`httpx` → Ollama** | LangChain / LlamaIndex | A framework hides the one thing that matters — the exact prompt |
| 9 | Structured output | **Pydantic → JSON schema → `format`** | prompt-only JSON | Grammar constraint makes an invalid label structurally impossible |
| 10 | Clustering | **HDBSCAN** | k-means | `k` unknown; noise must be allowed to stay noise |
| 11 | Vector search | **numpy cosine** | `sqlite-vec` | Unnecessary below ~1M vectors; addable later without schema change |
| 12 | Web | **FastAPI + Jinja + HTMX** | React SPA; Streamlit; Next.js | No build step; Streamlit would fight the approved mockups |
| 13 | Phase-1 UI | **Datasette** | build the real dashboard early | Browsable, faceted, queryable, day one, zero code |
| 14 | Charts | **Server SVG + Observable Plot** | D3; Chart.js | Most of it is static geometry; Plot only where hover earns it |
| 15 | Scheduler | **`launchd`** | `cron` | `cron` never fires while the machine is asleep and never catches up |
| 16 | Config | **TOML, hashed to a version** | constants in code; DB-only | Diffable, reviewable in a PR, and reproducible |
| 17 | Tests | **Golden-file parsers + pure verdict functions** | e2e, coverage targets | Drift is the risk; the verdict engine is pure and free to test |

---

## 2. Process architecture

The naive design is one daemon doing everything. That is wrong here, because the
components have incompatible resource and failure profiles: the collector must be
up whenever anyone is working, the enricher wants 3 GB of RAM at 2am, and the
dashboard is used for four minutes a week.

**Three processes, coordinated only through SQLite and the filesystem.**
No message bus, no queue, no supervisor beyond `launchd`.

```
   Claude Code                    the user's machine
   ───────────                    ──────────────────

   ~/.claude/projects/*.jsonl ──┐
   OTLP → 127.0.0.1:4318 ───────┤
   hooks → spool/*.json ────────┤        ┌──────────────────┐
   ~/.codex/… session logs ─────┼───────▶│   mui-collect    │  always on
   delegations.jsonl (wrapper) ─┘        │  no parsing      │  launchd KeepAlive
                                         └────────┬─────────┘
                                                  │ append only
                                         ┌────────▼─────────┐
                                         │    raw_event     │  immutable
                                         └────────┬─────────┘
                                                  │
                                         ┌────────▼─────────┐
                                         │    mui-batch     │  02:00 + hourly
                                         │  normalise       │  launchd calendar
                                         │  → enrich        │
                                         │  → verdicts      │
                                         └────────┬─────────┘
                                                  │
                    work_unit · api_call · tool_call · delegated_call
                    classification · outcome_signal · verdict
                                                  │
                                         ┌────────▼─────────┐
                                         │     mui-web      │  on demand
                                         │  + Datasette     │  dies when idle
                                         └──────────────────┘
```

| Process | Lifetime | Does |
|---|---|---|
| **`mui-collect`** | Always on (`launchd` `KeepAlive`) | Transcript watcher, Codex log watcher, hook-spool drain, OTLP receiver on `127.0.0.1:4318`. Writes **only** to `raw_event`. |
| **`mui-batch`** | Scheduled (02:00 + hourly light pass) | Normalise → enrich → verdicts, as ordered phases in one process. |
| **`mui-web`** | On demand (`mui open`) | FastAPI, dies when idle. |

Plus **`mui`**, a `typer` CLI that is the front door: `mui status`, `mui backfill`,
`mui reclassify --since`, `mui doctor`, `mui open`.

### 2.1 The load-bearing decision

**`mui-collect` does no interpretation.** It extracts just enough to get a
`session_id` and a content hash, appends the raw payload, and moves on.

It therefore *cannot* be broken by a schema change, because it does not
understand the schema. All parsing lives in `mui-batch`, where a failure is
recoverable by fixing the parser and re-running over `raw_event`. This turns the
PRD's graceful-degradation promise (§5.1) from an aspiration into a structural
property of the system.

Collapsing normalise and enrich into one scheduled process is deliberate too:
it means **at most two writers ever touch the database**, so SQLite's
single-writer model is a non-issue rather than a source of intermittent
`database is locked` errors that appear only under load and only at night.

---

## 3. Language and runtime

**Python 3.12+, managed with `uv`.**

The deciding factor is the enrichment plane. Excerpt building, embedding,
clustering, percentile cohorts and calibration are all Python-native work
(`numpy`, `scikit-learn`, `hdbscan`), and that is the half of the system with
real algorithmic content. Everything else — tailing files, receiving OTLP,
serving a local page — is equally easy in either language.

*The honest alternative is TypeScript*, and it is not a bad answer: Claude Code's
own ecosystem is TS, hooks are JSON-over-stdio and language-agnostic, and one
Node process could run the whole thing. It loses on the analytics side and would
mean either reimplementing clustering or shelling out to Python anyway.

Tooling: **`uv`** (environment, dependencies, lockfile, `uv run`), **`ruff`**
(lint + format), **`pytest`**.

### 3.1 Pydantic is not optional here

The single largest risk in the project is transcript schema drift. Pydantic
models with `extra="ignore"` give exactly the defensive parsing that risk
demands:

- unknown fields are dropped without error
- missing fields raise a countable `ValidationError` rather than a `KeyError`
  three layers down
- **the count of validation failures *is* the schema-drift canary**

The same models generate the classifier's JSON schema (§7), so the taxonomy has
one definition rather than two that quietly diverge.

---

## 4. Hooks must not be Python

This is the single most important implementation detail for the zero-added-latency
requirement. Hooks fire constantly, and Python interpreter startup is 50–100 ms.
A Python hook would be a measurable tax on every tool call.

Hooks receive their payload as JSON on stdin, so the hook can be a one-line shell
script that spools it and exits:

```sh
#!/bin/sh
# ~/.model-use-index/hooks/spool.sh — registered for every hook we consume
exec cat > "$HOME/.model-use-index/spool/$(date +%s)-$$-$PPID.json"
```

Roughly a millisecond. No interpreter, no network, no lock, no way to hang a
session. `mui-collect` drains the spool directory and deletes what it ingests.

**Use a spool directory, not a shared append-only file.** Appends under
`PIPE_BUF` to an `O_APPEND` file are atomic, but hook payloads can exceed it and
interleaved writes would corrupt records *invisibly* — the worst failure mode
available. One file per invocation costs nothing and cannot interleave.

---

## 5. Storage

**SQLite, WAL, `synchronous=NORMAL`, `busy_timeout=5000`.**

Plain `sqlite3` with SQL in `.sql` files — **no ORM.** The schema is analytical,
the queries *are* the product, and an ORM adds indirection with nothing in
return at this scale. `sqlite-utils` is worth having for ingest ergonomics and
ad-hoc work.

Migrations: numbered `.sql` files applied in order against a `schema_version`
table. Do not reach for Alembic.

### 5.1 DuckDB is a good idea later, not now

DuckDB reads a SQLite file directly and is dramatically better at the window
functions the cohort percentiles need. The trigger for adopting it is concrete:
**when a dashboard query exceeds ~300 ms.** Before that it is a second dependency
buying nothing. Because it is a read-side change only, deferring costs nothing
and adopting it later requires no migration.

### 5.2 Retention and backup

Not covered in the PRD, and it needs an answer before Phase 1 ships.

- **`raw_event` grows without bound** — realistically a few hundred MB a year of
  mostly text for one heavy user, which is affordable. Keep it. It is the only
  thing that makes re-derivation possible, and re-derivation is the whole
  recovery story.
- **Compress on age.** Rows older than 90 days can have their `payload` zstd-
  compressed in place; text compresses roughly 8–10×. Cheap, reversible, and
  keeps the file small enough to back up casually.
- **Backup is a file copy.** `sqlite3 .backup` to a dated file in the user's
  normal backed-up location, nightly, as the last phase of `mui-batch`. Keep
  seven. No other backup story is needed for a single-machine tool.
- **The database contains prompt text.** It should live somewhere covered by
  FileVault and should not be synced to a shared drive. Worth stating explicitly
  before someone helpfully puts it in Dropbox.

---

## 6. Classifier integration

Ollama's HTTP API directly, via `httpx`. **No LLM framework.** LangChain,
LlamaIndex and friends are pure overhead for a single structured call, and they
obscure the one thing that matters here — exactly what text went into the prompt.

```python
schema = Classification.model_json_schema()      # the Pydantic model, §3.1
r = httpx.post("http://localhost:11434/api/chat", timeout=120, json={
    "model": "qwen3:4b",
    "format": schema,                            # grammar-constrained sampling
    "options": {"temperature": 0, "num_ctx": 4096},
    "keep_alive": "30m",
    "messages": [{"role": "user", "content": prompt_with_schema_restated}],
})
result = Classification.model_validate_json(r.json()["message"]["content"])
```

One Pydantic model defines the taxonomy, generates the grammar, and validates the
result. Three properties from one definition.

**Concurrency is 1.** Ollama on 8 GB gains nothing from parallel requests and
will thrash. Keep the model warm for the batch, then let it unload.

> ⚠ **The failure mode that sinks a v1.** Ollama never shows the model the
> schema — it only constrains sampling. The schema and the enum values **must
> also be restated in the prompt text.** Grammar constraint alone yields
> structurally perfect JSON containing semantic nonsense, which is far harder to
> notice than a parse error.

---

## 7. Clustering and vectors

`nomic-embed-text` via Ollama; vectors stored as BLOB. At this volume plain
`numpy` cosine similarity is fine — **`sqlite-vec` is unnecessary below roughly a
million vectors** and can be added later without a schema change.

Cluster with **HDBSCAN**, not k-means: `k` is unknown, cluster sizes are wildly
uneven, and — most importantly — HDBSCAN labels noise points as noise instead of
forcing every one-off task into some cluster. A subagent recommendation built on
forced assignments would be confidently wrong, which is the specific way this
analysis fails if you get it wrong.

---

## 8. Web

**FastAPI + Jinja + HTMX. No build step, no npm, no bundler.**

The dashboard is tables, a matrix, and a handful of charts. A React SPA would add
a toolchain, a dev server and a deployment story to a tool that runs on
`localhost` for one person. HTMX covers the interactions that actually exist
here — filter, sort, drill through, expand a row.

Charts: server-rendered inline SVG for anything static (the sankey and the matrix
are pure geometry, as the mockups demonstrate), and **Observable Plot** from a
CDN where hover or zoom genuinely helps. Not D3 directly.

**Two rejections worth recording.** *Streamlit* is faster to start and worse to
live with — the rerun model, awkward tables, and no real path to the designed
mockups; now that those mockups exist, Streamlit would spend the whole build
fighting them. *Next.js* is an entire deployment story for a page served to one
browser on the same machine.

### 8.1 Use Datasette in Phase 1

Point it at the SQLite file and there is a browsable, queryable UI with facets
and a SQL console on day one, for zero code. It covers the "is the data right?"
period completely, and it *is* the SQL console the PRD asks for.

Build the designed dashboard in Phase 3, when there is something worth designing
around — and keep Datasette afterwards for ad-hoc work.

---

## 9. Scheduling — and one real gotcha

**`launchd`, not `cron`.**

On macOS, **`cron` simply does not fire while the machine is asleep and never
catches up.** A 02:00 nightly job on a laptop that closes at 23:00 runs
approximately never. `launchd`'s `StartCalendarInterval` fires on wake for missed
intervals, which is exactly the semantics a batch job on a laptop needs.

Two jobs:

| Job | Config |
|---|---|
| `com.hg.mui.collect` | `KeepAlive` true, `RunAtLoad` true |
| `com.hg.mui.batch` | `StartCalendarInterval` 02:00, plus a light hourly normalise-only pass so `mui status` is never a day stale |

The enrichment phase should also check for AC power and skip to the next wake if
on battery — a 30-minute local-model batch on battery is an unkind thing to do to
someone's laptop.

---

## 10. Config and versioning

One `~/.model-use-index/config.toml` for paths, model choice and thresholds —
plus the tier matrix and the verdict rules as **TOML, not code**, so they are
diffable, reviewable in a PR, and hashable.

On load, the hash becomes `rules_version`. The same pattern gives
`classifier_version` (model + prompt hash + taxonomy version) and
`registry_version`.

That is what makes the PRD's reproducibility promise real: every derived number
traces back to a raw event plus three named, versioned configs, and changing a
threshold **re-derives** history rather than silently rewriting it.

---

## 11. Testing

Two kinds carry almost all the value.

**Golden-file parser tests.** Capture real transcript, OTel, hook and Codex
records as fixtures; assert the normaliser's output. These are the regression
suite for schema drift — the thing most likely to break — and they are nearly
free to produce, because Phase 0 collects the samples anyway.

**Pure-function tests on the verdict engine.** The verdict rules are
deterministic and side-effect free, which is why it was possible to verify all 28
reference-report rows before writing any of the system. That test is the seed of
the suite, and it already exists.

Deliberately *not* worth much here: mocking Ollama, end-to-end browser tests,
coverage targets. This is internal tooling for one machine.

---

## 12. Repo layout

```
model-use-index/
├── pyproject.toml            # uv, ruff, pytest
├── config.toml.example
├── migrations/               # 001_init.sql, 002_allowance.sql, …
├── launchd/                  # two .plist templates
├── hooks/spool.sh            # §4
├── wrappers/codex            # PRD §5.1 E2 — call-site attribution
├── src/mui/
│   ├── models.py             # Pydantic — one definition of every record
│   ├── collect/              # transcript.py otel.py hooks.py codex.py
│   ├── normalize/            # work_unit.py reconcile.py delegation.py
│   ├── enrich/               # excerpt.py classify.py signals.py allowance.py
│   ├── verdict.py            # pure functions
│   ├── analyses/             # a1_over.py a2_under.py a3_cluster.py …
│   ├── web/                  # FastAPI + Jinja + HTMX
│   └── cli.py                # typer
└── tests/fixtures/           # golden records from Phase 0
```

The `collect / normalize / enrich` split is the capture architecture made
physical, so the boundary between *captured* and *interpreted* is visible in the
directory tree and hard to erode by accident.

---

## 13. Observing the observer

This runs unattended, and silent failure is the primary risk — **a tool that
stopped ingesting three weeks ago but still renders a confident dashboard is
worse than no tool.**

`mui doctor` is therefore a first-class deliverable, not a nice-to-have. It
checks:

- last event ingested per source, with a staleness threshold each
- `raw_event` → `work_unit` watermark lag
- Pydantic validation-failure rate (the schema-drift canary, §3.1)
- reconciliation delta per provider
- orphaned delegations
- classifier queue depth and last successful batch
- allowance-model fit quality and `limit_event` count
- free disk, and database size against the compression threshold

The same numbers back the data-quality view in the dashboard. `mui-batch` writes
a one-line summary to a log the dashboard surfaces, so *"when did this last
actually work?"* is always answerable in one glance.

---

## 14. Build order for Phase 1

Sequenced so that something is verifiable at the end of each step, rather than
integrating everything at the end and debugging a black box.

| Step | Build | Verifiable by |
|---|---|---|
| 1 | Schema + migrations + `mui doctor` skeleton | `mui doctor` runs against an empty DB and reports every source as absent |
| 2 | Transcript collector → `raw_event`, plus backfill | Row count matches the JSONL line count on disk |
| 3 | Pydantic models + normaliser → `work_unit` / `api_call` | Token totals reconcile with `/usage` within 2% over 7 days |
| 4 | Datasette on the file | You can browse and query real data — first moment the project feels real |
| 5 | OTel receiver + reconciliation | Delta between sources < 2%, reported by `mui doctor` |
| 6 | Hooks + spool drain | `PreModelSwitch` events appear and match sessions you remember escalating |
| 7 | `codex` wrapper + Codex log tailer | ≥ 98% of Codex sessions join to a parent work unit |
| 8 | Model registry + allowance model | Allowance percentages sum to 100 per pool; `limit_event` rows appear |

Step 4 is placed early on purpose. Being able to *look at* the data before any
enrichment exists is what catches capture bugs while they are still cheap.

---

## 15. Open implementation questions

Distinct from the PRD's open questions, which are about the product. These are
about the build.

1. **OTLP receiver: full OpenTelemetry Collector, or ~100 lines of FastAPI?**
   The collector is the supported path but adds a binary, a config format and a
   process to supervise. A minimal receiver that accepts `http/protobuf` and
   writes to `raw_event` is likely enough for one machine, and keeps everything
   in one process. Lean minimal; revisit if the protobuf handling gets fiddly.
2. **File watching: `watchdog` or `fswatch`?** `watchdog` keeps it in-process;
   FSEvents on macOS can coalesce and occasionally miss under rapid appends, so
   either way a periodic reconcile sweep is needed as a backstop. Do not rely on
   events alone.
3. **What happens if the `codex` wrapper is bypassed?** Someone calls the real
   binary directly, or a tool invokes it by absolute path. Detection: a Codex
   session log with no matching sidecar. That already surfaces as `orphaned`, but
   we should decide whether to attempt timestamp-based joining for those or
   simply report them.
4. **Does `mui-collect` need to survive Ollama being absent?** Yes — but confirm
   nothing in the collect path touches Ollama at all, which is the intent of the
   plane split.
5. **Compression threshold and format.** zstd via `python-zstandard` adds a
   dependency; `zlib` is stdlib and roughly 30% worse. Probably not worth the
   dependency. Decide once real data volumes are known.

---

## 16. Packaging, and a thought for later

For v1: a git repo and a `make install` that writes the plists, registers the
hooks, and installs the `codex` wrapper.

Worth knowing for the eventual multi-user phase: the hook registrations, settings
and wrapper are exactly the shape of a **Claude Code plugin**. Packaging the
client half as a plugin would make team rollout an install command rather than a
runbook. Not for v1 — but it argues for keeping all client-side configuration in
one directory now, rather than scattering it through the codebase and having to
untangle it later.