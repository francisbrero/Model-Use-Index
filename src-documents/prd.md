# PRD — Model Use Index

**A local-first observability and right-sizing system for Claude Code usage**

| | |
|---|---|
| **Owner** | Francis Brero |
| **Status** | Draft v0.2 for review — not yet built |
| **Date** | 9 September 2026 (v0.2) |
| **Scope** | Internal tooling, HG Insights. Single-operator deployment first. |
| **Changed in v0.2** | Currency is allowance headroom, not dollars (§2.1). Delegated Codex agents added as a required capture source (§5.1 E). Anthropic-side gateway dropped (§5.2). |
| **Target artifact** | The *Model Use Index* report (see §2) |

---

## 1. Problem

We are spending real money on frontier-model tokens inside Claude Code, and we
have no idea whether we are spending it well. The current state of knowledge is
a monthly invoice and a vague sense that Opus is expensive.

Three specific questions are unanswerable today:

1. **Where are we over-provisioning?** How much scarce frontier-model headroom
   goes on work a cheap model would have finished correctly? We are on seat
   subscriptions, so this is not an invoice question — it is why someone gets
   rate-limited on Thursday afternoon (§2.1).
2. **Where are we under-provisioning?** Which tasks are failing, thrashing, or
   burning ten turns on a cheap model when one turn on a strong model would
   have closed it? This is the more expensive failure and the harder one to see,
   because it shows up as *wasted engineer time*, not as a line item.
3. **What work is repetitive enough to deserve a purpose-built subagent** with a
   pinned cheap model, a narrow tool allowlist, and a tuned prompt?

A fourth question sits underneath all three: **how much of this work is not
visible at all?** Codex subagents invoked from inside Claude Code consume a
separate allowance that no Claude Code telemetry can see (§5.1 Source E).

A fifth follows once the rest are instrumented: **which
subagents and task types actually make people angry?** Frustration is a leading
indicator of a badly-scoped agent, and it is currently invisible.

### 1.1 Why existing tooling doesn't answer this

- `/usage` and `/insights` give per-session cost. They do not classify *what the
  work was*, so they cannot tell you whether the spend was appropriate.
- Cloud FinOps tools (Cloudability, Vantage, Finout) allocate cost to a
  department tag. They stop at "Engineering spent $12k." They have no semantic
  layer, and on a seat plan they have no dollars to allocate either.
- LLM observability platforms (Langfuse, Helicone, Portkey) capture traces.
  They render what happened; they do not judge whether the model choice was right.

The missing piece in all of them is a **semantic enrichment layer** — a cheap
classifier that reads each unit of work and labels it, so that cost can be
grouped by *kind of work* rather than by *session id*.

---

## 2. Target artifact

The primary deliverable is a report we are calling the **Model Use Index**.
One row per (department × model × activity × work type × complexity), with a
provisioning verdict and its headroom impact attached.

| Column | Type | Source |
|---|---|---|
| `department` | dimension | Config / user mapping. Constant for v1 (single operator). |
| `provider` | dimension | Captured. `anthropic` \| `openai` \| … |
| `allowance_pool` | dimension | Which seat allowance this drew from. **Consumption never sums across pools.** |
| `ai_model` | dimension | Captured — exact model string incl. version pin |
| `ai_activity` | classified enum | Local classifier |
| `work_type` | classified enum | Local classifier |
| `task_complexity` | classified enum | Local classifier |
| `model_justification` | **derived verdict** | Rules engine (§8) |
| `allowance_pct` | **primary measure** | Share of the pool's period allowance consumed |
| `list_value_usd` | secondary measure | Notional. Ranking aid only — see below. |

### 2.1 The unit of account is headroom, not dollars

We are on **seat subscriptions, not metered API billing.** This is not a
detail; it changes what the report is for.

Running Opus on trivial work does not move an invoice. It burns the 5-hour and
weekly seat allowance faster and gets someone rate-limited on Thursday
afternoon. The scarce resource is **frontier-model headroom**, and that is what
the report must measure.

So the primary measure is **share of allowance consumed**, per pool. A dollar
figure is still computed — it is useful for ranking and for talking to Finance —
but it is labelled *notional list value* everywhere it appears, because nobody
can reconcile it against anything we actually pay.

Three consequences worth stating up front:

- **Recommendations become verifiable.** "Saves $909/month" is a promise we
  cannot keep on a subscription. "Reclaims 6.2 points of weekly Opus allowance"
  is a claim that can be checked the following week by watching whether the
  limit-hit events stop.
- **The finding becomes personally felt.** Nobody changes their workflow over
  $900 of notional spend. Getting rate-limited mid-afternoon is a real,
  irritating, personal cost — and this report says exactly which
  low-complexity work ate the headroom.
- **Pools do not add up.** Anthropic allowance and OpenAI/Codex allowance are
  separate ceilings. Summing them into one number would be meaningless, and
  worse, would hide the one move that matters most (§10 A6).

> ⚠ **Honest caveat on the weighting.** Per-token allowance weight may well
> track list price closely, in which case allowance units are close to a
> rescaled dollar figure. **The value of this reframe is not the weighting —
> it is the fixed denominator and the per-pool split.** A percentage of a
> ceiling you actually hit means something; a dollar figure on a plan with no
> per-token invoice does not.

### 2.2 Supporting columns

Not in the reference report, but required, because they are what make the
verdict trustworthy:

| Column | Why |
|---|---|
| `turns`, `tool_calls` | Effort proxy; the denominator for "did it go well" |
| `retry_rate`, `error_rate` | Under-provisioning evidence |
| `cache_read_tokens` / `cache_creation_tokens` | Cache efficiency is a separate lever from model choice |
| `agent_type` | Which subagent did this; null for main thread |
| `delegated_to` | Set when work was handed to an external agent (§5.1 Source E) |
| `frustration_score` | Phase 3 |
| `confidence` | Classifier self-reported; gates whether a row is actionable |

The report must be filterable and drillable — a row is not useful unless you can
click through to the three heaviest sessions behind it.

**Non-goal for v1:** real-time. A report fresh as of last night is entirely
sufficient for a decision loop that runs weekly. This single decision removes
most of the engineering risk in the project.

---

## 3. Goals and non-goals

### Goals

- **G1** — Attribute every unit of allowance consumption to a classified unit of
  work, per pool.
- **G2** — Produce a defensible over/under-provisioning verdict per unit of work,
  with the evidence attached.
- **G3** — Surface a ranked list of subagent candidates: recurring work patterns
  where a pinned cheap model would return real headroom.
- **G4** — Run entirely on the operator's laptop. No prompt content leaves the machine.
- **G5** — Add zero measurable latency to the interactive coding loop.
- **G6** — Account for work delegated to **external agents invoked from inside
  Claude Code** — today, Codex subagents. Spend that is invisible is worse than
  spend that is unmeasured, because it makes the rows that use it look cheap.

### Non-goals (v1)

- Multi-user / team rollout. The schema must not preclude it (§6.2) but nothing
  is built for it.
- Real-time alerting or budget enforcement.
- Automatic model routing. This system *recommends*; a human changes the config.
- General coverage of non-Claude-Code AI usage (IDE autocomplete, chat UI).
  G6 is narrower: only agents **Claude Code itself invokes**.
- An Anthropic-side gateway. See §5.4 — this is now a decided "no", not a defer.
- Anything that requires a server we have to operate.

### Success criteria

| | Measure | Target |
|---|---|---|
| Coverage | % of allowance consumption attributable to a classified work unit, **including delegated calls** | > 95% |
| Attribution | % of Codex sessions correctly joined to a parent work unit | > 98% |
| Classifier agreement | Agreement with hand-labelled 200-row gold set on `work_type` and `task_complexity` | > 80% |
| Allowance model | Predicted vs. observed limit-hit events over 30 days | within 15% |
| Cost of the system | Classification compute + storage | $0 marginal, < 30 min/night |
| Actionability | Distinct right-sizing actions produced in month one | ≥ 3 |
| Intrusiveness | p95 added latency to an interactive turn | 0 ms |

That last one is a hard constraint, and it is why the classifier runs as a
batch job rather than inline.

---

## 4. Constraints and environment

- **Hardware:** Apple Silicon, M3 or better, **8 GB unified memory**. This is the
  binding constraint on the whole design. After macOS, an IDE, a browser and
  Claude Code itself, the realistic budget for a local model is **~3 GB
  resident, 4 GB at an absolute stretch**.
- **OS:** macOS. Single machine.
- **Auth:** Claude Code subscription auth (see §5.4 — this materially constrains
  the gateway option).
- **Providers:** Predominantly Anthropic, but the design must accommodate other
  providers, because the target report has a `gpt-4.1` row in it. Model tiering
  must be provider-agnostic.

---

## 5. Architecture

Four planes, deliberately decoupled so each can fail independently:

```
  ┌─────────────────────────────────────────────────────────────┐
  │  CAPTURE   transcript │ OTel │ hooks │ delegated-agent logs  │
  └────────────────────┬────────────────────────────────────────┘
                       │  raw events (append-only, never mutated)
  ┌────────────────────▼────────────────────────────────────────┐
  │  NORMALISE  reconcile sources → canonical `work_unit`        │
  │             join delegated calls to their parent             │
  └────────────────────┬────────────────────────────────────────┘
                       │
  ┌────────────────────▼────────────────────────────────────────┐
  │  ENRICH     local classifier (batch, nightly)                │
  │             + deterministic outcome-signal extractor         │
  │             + allowance model  + verdict rules engine        │
  └────────────────────┬────────────────────────────────────────┘
                       │
  ┌────────────────────▼────────────────────────────────────────┐
  │  SERVE      SQLite  →  local dashboard  +  SQL console       │
  └─────────────────────────────────────────────────────────────┘
```

**Design principle:** the raw event store is append-only and is never
overwritten by enrichment. Classification labels live in a separate table keyed
by `work_unit_id` plus a `classifier_version`. When the taxonomy changes — and
it will — we re-run enrichment over history rather than losing it.

### 5.0 The question underneath the question

"Which capture mechanism" reduces to **"where does the text come from."**
Split the problem and most of it collapses:

- **Consumption accounting is solved.** OTel gives tokens, model, session and
  `prompt.id` correlation through a documented, supported interface. Low risk,
  no decisions.
- **Semantic capture is the real question**, because classification needs
  message text, and only the transcript has it at acceptable risk.
- **Delegated work is the blind spot**, and it needs its own source entirely.

Everything below follows from that.

### 5.1 Capture sources

#### Source A — Transcript tailer (primary; required)

Claude Code writes append-only JSONL session transcripts under
`~/.claude/projects/<slugified-cwd>/<session-id>.jsonl`. A `fswatch`/`watchdog`
process tails these and appends new records to our raw store.

*Gives us:* full message text (needed for classification), per-assistant-message
`message.usage` token counts (`input_tokens`, `output_tokens`,
`cache_creation_input_tokens`, `cache_read_input_tokens`), the model string,
tool calls with their inputs, tool results with `is_error`, `cwd`, `gitBranch`,
`version`, and the `uuid`/`parentUuid` chain that rebuilds turn structure.

*Why primary — and this was under-weighted in v0.1:* **it is retroactive.**
Every other source starts collecting from zero. The transcript gives us months
of history on day one. For a tool whose entire purpose is finding patterns
*across* sessions, that is the difference between a real finding in a day and
waiting a month for enough data to say anything. It also means the classifier
can be calibrated against work the operator actually remembers doing.

> ⚠ **Known risk.** This schema is internal and unstable across Claude Code
> versions; Anthropic explicitly advises against depending on it. Mitigations:
> (a) the parser is defensive — unknown fields ignored, missing fields produce a
> `parse_degraded` flag rather than an exception; (b) a schema-drift canary
> alerts if the share of records failing to yield token counts crosses 1%;
> (c) the `version` field is recorded on every record so drift bisects to a
> release; (d) Source B is the cross-check.
>
> **The risk asymmetry is what settles this.** If the parser breaks, the tool
> degrades, the files are still on disk, and a fixed parser re-ingests
> everything. Nothing is lost or corrupted. A gateway failure, by contrast,
> breaks the workday mid-task. One risk lands on the observability system; the
> other lands on the thing being observed.

#### Source B — Native OpenTelemetry export (primary; required)

Claude Code emits OTLP metrics and logs when `CLAUDE_CODE_ENABLE_TELEMETRY=1`.
A local collector (or a ~100-line OTLP receiver) writes to the same store.

*Gives us:* `claude_code.cost.usage` and `claude_code.token.usage` with `model`,
`session.id` and token-type attributes; events including
`claude_code.api_request`, `api_error`, `tool_result`, `tool_decision`,
`user_prompt`, `assistant_response`. Critically it carries `prompt.id`, which
correlates every event from a single user prompt, and `client_request_id` per
API call.

*Why it earns its place:* it is a **supported, documented interface**, unlike the
transcript schema. It is the authoritative source for token counts, and
`prompt.id` gives turn correlation more reliable than walking `parentUuid`.

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_LOG_USER_PROMPTS=1
export OTEL_LOG_TOOL_DETAILS=1
export OTEL_METRIC_EXPORT_INTERVAL=30000
```

> **Security note.** These belong in the operator's shell profile, outside any
> repo. There is a documented exfiltration technique where a hostile repo's
> checked-in settings point telemetry headers at an attacker-controlled helper
> command. Our ingest endpoint is `localhost` only.

Research surfaced an undocumented `OTEL_LOG_RAW_API_BODIES=1` reported to emit
full request/response bodies. **Unverified.** If real, it would give us the
assembled context window — see A4 in §10. Phase 0 tests it.

#### Source C — Hooks (targeted; required)

Not bulk capture — a small set of hooks recording facts the message stream
cannot express. Each writes one JSON line to a file and exits 0. A hook that
hangs, hangs the session.

| Hook | Recorded | Why |
|---|---|---|
| `SubagentStart` / `SubagentStop` | `agent_id`, `agent_type`, parent `session_id`, duration | The only reliable source for *which named subagent* did the work |
| **`PreModelSwitch` / `PostModelSwitch`** | from-model, to-model, timestamp | See below |
| `PreCompact` | timestamp, session | Context-pressure and consumption event |
| `Stop` / `StopFailure` | completion vs. interruption | Frustration signal |
| `PreToolUse` (Bash only) | command verb | Detects delegation to an external agent (§ Source E) |

**`PreModelSwitch` deserves separate billing.** When someone escalates
Sonnet → Opus mid-session, that is a human explicitly saying *"this model is not
working for this task."* It is ground truth for under-provisioning that needs no
classifier and no thresholds — and it produces a **free labelled dataset** to
calibrate everything else against. The under-provisioning model can be
bootstrapped from escalation events alone. This moves hooks from "useful
supplement" to load-bearing for §10 A2.

#### Source E — Delegated-agent logs (required; the v0.1 blind spot)

**Codex subagents are invoked from inside Claude Code today, and none of
Sources A, B or C can see what they cost.** Those calls never touch Anthropic's
API: no transcript API records, no OTel token metrics, and an Anthropic-side
gateway would not see them either.

What Claude Code *does* record is the shell-out — a `Bash` tool call with the
prompt as an argument, a duration, an exit status, and the returned text. So a
delegated work unit appears with its *effort* visible and its *consumption
absent*, which makes those rows look artificially **cheap**. That is worse than
missing data: it inverts the verdict on exactly the rows we most want to judge.

Capture is two parts:

**E1 — Tail the external agent's own session records.** Codex keeps local
session logs with its own token accounting, structurally the same problem as
Source A. *The exact path and record schema must be confirmed empirically —
Phase 0.* An OpenAI-side gateway is the fallback if the logs prove insufficient,
and carries none of the Anthropic-gateway problems (no subscription-OAuth
question, no prompt-cache defeat risk on our primary provider).

**E2 — Stamp the parent at the call site.** Timestamp-matching a Codex session
to the Claude Code turn that spawned it would mostly work and occasionally lie.
The clean answer is a thin wrapper on the `codex` invocation that writes a
sidecar record joining the Codex session id to the parent `prompt_id`:

```bash
#!/usr/bin/env bash
# ~/.local/bin/codex — wrapper, ahead of the real binary on PATH
run_id="$(uuidgen)"
printf '{"run_id":"%s","parent_prompt_id":"%s","cwd":"%s","ts":"%s"}\n' \
  "$run_id" "${CLAUDE_PROMPT_ID:-unknown}" "$PWD" "$(date -Iseconds)" \
  >> ~/.model-use-index/delegations.jsonl
CODEX_RUN_ID="$run_id" exec /opt/homebrew/bin/codex "$@"
```

We control how these subagents are invoked, so this is a one-line change at the
call site rather than an inference problem. Done properly it yields true
cross-provider attribution, which is what makes multi-model rows trustworthy.

### 5.2 Why there is no Anthropic gateway

v0.1 deferred this to Phase 4 as conditional. It is now a **decided no**, for
four reasons that compound:

| Concern | Detail |
|---|---|
| **It is not needed** | Coverage is Claude-Code-only. Sources A + B + C cover it. The one thing a gateway uniquely provides — the assembled context window — is wanted for one secondary analysis (A4) and may be obtainable from `OTEL_LOG_RAW_API_BODIES`. |
| **Subscription auth / ToS** | Subscription OAuth passes a gateway only if no gateway credential is set *and* `anthropic-beta` is forwarded verbatim. Separately, Anthropic's Feb 2026 policy restricts subscription tokens to Claude Code and claude.ai; whether a personal passthrough proxy is in scope is **not settled by any public statement.** We are on seats. This alone is disqualifying without a written answer. |
| **Silent cache defeat** | A proxy that reorders or merges the `system` array, or stringifies block content, breaks prompt caching with **no error** — visible only as elevated uncached `input_tokens`. A consumption tool that inflates the consumption it measures is a special kind of bad. |
| **Risk lands in the wrong place** | Every other source fails toward "the tool is degraded." This one fails toward "the workday stopped." |

Also on the record, if this is ever revisited: LiteLLM allowlists
`anthropic-beta` against Anthropic's explicit gateway guidance, has recurring
bugs where request bodies persist as `{}` and passthrough requests record
`spend: 0.0`, and shipped credential-stealing malware on PyPI for ~40 minutes in
March 2026. If a gateway is ever needed, `mitmproxy` in reverse mode is the
lighter, better-understood option, and an OpenAI-side proxy (Source E fallback)
is a different and far safer proposition than an Anthropic-side one.

### 5.3 Source reconciliation

Sources share `session_id`; A and B additionally share `message.uuid`.

1. Join B→A on `session.id` + `message.uuid` where present.
2. Fall back to `session.id` + timestamp window (±2 s).
3. **Consumption has exactly one authoritative source per provider** — OTel for
   Anthropic, the agent's own logs for delegated providers. Other sources record
   a `reconciliation_delta` but never contribute tokens. Three sources with
   different clocks is precisely how double-counting happens; this rule goes in
   on day one, not in Phase 3.
4. Text content always comes from A (or E1 for delegated work).
5. Records present in exactly one source are kept with a `sources` bitmask;
   single-source coverage is exposed as a data-quality metric.
6. Delegated calls join on `run_id` from the E2 sidecar; a delegation with no
   matching agent-log record is flagged `orphaned` and surfaced, never silently
   dropped.

A persistent reconciliation delta above 2% is a bug, not rounding.

### 5.4 Subagent attribution — open question

Research returned **contradictory** accounts of how Task-tool subagent turns
appear on disk: inlined into the parent transcript flagged `isSidechain: true`,
versus written to separate transcript files with their own `sessionId`. Likely
version-dependent.

**Resolve empirically in Phase 0** by spawning a known subagent and diffing
`~/.claude/projects/`. G3 and Phase 3 both depend on attributing consumption to
the agent that spent it; an incorrect assumption here silently misattributes a
large fraction to the main thread. The `SubagentStart`/`SubagentStop` hooks are
the belt-and-braces answer whichever layout is correct.

---

## 6. Data model

SQLite, WAL mode, single file at `~/.model-use-index/store.db`. A heavy user's
year is a few hundred MB of text and well under a million work units. SQLite
handles that without breathing hard, needs no daemon, backs up trivially, and is
queryable by anything the operator already has. Do not reach for Postgres.

### 6.1 Core tables

```sql
-- Immutable raw capture. Never updated, never deleted.
CREATE TABLE raw_event (
  id            INTEGER PRIMARY KEY,
  source        TEXT NOT NULL,   -- 'transcript'|'otel'|'hook'|'codex'|'delegation'
  ingested_at   TEXT NOT NULL,
  session_id    TEXT,
  payload       TEXT NOT NULL,   -- verbatim JSON
  content_hash  TEXT NOT NULL UNIQUE
);

-- The unit of analysis: one user prompt and everything it caused,
-- within one agent context.
CREATE TABLE work_unit (
  id                     TEXT PRIMARY KEY,   -- prompt_id, or synthesised
  session_id             TEXT NOT NULL,
  parent_work_unit_id    TEXT,
  agent_type             TEXT,               -- NULL = main thread
  agent_id               TEXT,
  started_at             TEXT NOT NULL,
  ended_at               TEXT,
  cwd  TEXT,  repo TEXT,  git_branch TEXT,  cc_version TEXT,
  sources                INTEGER NOT NULL,   -- bitmask
  parse_degraded         INTEGER DEFAULT 0
);

-- One row per API call, whichever provider served it.
CREATE TABLE api_call (
  id                      TEXT PRIMARY KEY,   -- client_request_id / codex call id
  work_unit_id            TEXT NOT NULL REFERENCES work_unit(id),
  delegated_call_id       TEXT REFERENCES delegated_call(id),  -- NULL if direct
  message_uuid            TEXT,
  provider                TEXT NOT NULL,      -- 'anthropic'|'openai'
  allowance_pool          TEXT NOT NULL,      -- 'anthropic-seat'|'openai-seat'|'openai-api'
  model                   TEXT NOT NULL,      -- exact string, version pin included
  model_tier              TEXT NOT NULL,      -- resolved via model_registry
  input_tokens            INTEGER NOT NULL,
  output_tokens           INTEGER NOT NULL,
  cache_creation_tokens   INTEGER NOT NULL DEFAULT 0,
  cache_read_tokens       INTEGER NOT NULL DEFAULT 0,
  allowance_units         REAL NOT NULL,      -- computed, §6.3
  list_value_usd          REAL NOT NULL,      -- notional; ranking aid only
  registry_version        TEXT NOT NULL,
  latency_ms              INTEGER,
  is_error                INTEGER DEFAULT 0,
  reconciliation_delta    REAL DEFAULT 0.0,
  started_at              TEXT NOT NULL
);

-- Work handed to an external agent invoked from inside Claude Code.
CREATE TABLE delegated_call (
  id                 TEXT PRIMARY KEY,    -- run_id from the wrapper sidecar
  work_unit_id       TEXT REFERENCES work_unit(id),   -- NULL until joined
  agent              TEXT NOT NULL,       -- 'codex'
  external_session   TEXT,                -- the agent's own session id
  invoked_at         TEXT NOT NULL,
  duration_ms        INTEGER,
  exit_status        INTEGER,
  join_method        TEXT NOT NULL,       -- 'sidecar'|'timestamp'|'unjoined'
  orphaned           INTEGER DEFAULT 0    -- sidecar with no agent-log match
);

CREATE TABLE tool_call (
  id TEXT PRIMARY KEY,
  work_unit_id TEXT NOT NULL REFERENCES work_unit(id),
  tool_name TEXT NOT NULL,
  target TEXT,               -- file path, command verb, URL host — normalised
  is_delegation INTEGER DEFAULT 0,
  is_error INTEGER DEFAULT 0,
  duration_ms INTEGER,
  started_at TEXT NOT NULL
);

-- Enrichment output. Separate, versioned, re-runnable.
CREATE TABLE classification (
  work_unit_id TEXT NOT NULL REFERENCES work_unit(id),
  classifier_version TEXT NOT NULL,   -- model + prompt hash + taxonomy version
  ai_activity TEXT NOT NULL,
  work_type TEXT NOT NULL,
  task_complexity TEXT NOT NULL,
  stakes TEXT NOT NULL,               -- 'routine'|'high'
  confidence REAL NOT NULL,
  rationale TEXT,
  classified_at TEXT NOT NULL,
  PRIMARY KEY (work_unit_id, classifier_version)
);

-- Deterministic. No model involved.
CREATE TABLE outcome_signal (
  work_unit_id TEXT PRIMARY KEY REFERENCES work_unit(id),
  turns INTEGER, tool_calls INTEGER, tool_error_rate REAL,
  edit_thrash INTEGER,        -- max edits to a single file
  model_escalated INTEGER,    -- PreModelSwitch upward occurred
  compactions INTEGER, user_interrupted INTEGER,
  corrective_turns INTEGER, prompt_restated INTEGER, completed INTEGER
);

CREATE TABLE verdict (
  work_unit_id TEXT NOT NULL REFERENCES work_unit(id),
  rules_version TEXT NOT NULL,
  justification TEXT NOT NULL,        -- §8.2
  expected_tier TEXT NOT NULL, used_tier TEXT NOT NULL, tier_delta INTEGER NOT NULL,
  evidence TEXT,                      -- JSON: which signals fired
  headroom_reclaimable REAL,          -- allowance units, overprovisioned rows
  headroom_pool TEXT,                 -- which pool it would be returned to
  PRIMARY KEY (work_unit_id, rules_version)
);
```

### 6.2 Allowance model

The primary measure is modelled, not captured, so it is versioned and
calibrated like any other model in the system.

```sql
CREATE TABLE model_registry (
  version TEXT NOT NULL,
  provider TEXT NOT NULL,
  model_pattern TEXT NOT NULL,     -- glob; matches version-pinned strings
  tier TEXT NOT NULL,              -- 'small'|'mid'|'frontier'
  allowance_pool TEXT NOT NULL,
  au_per_mtok_in REAL NOT NULL,    -- allowance weight, not price
  au_per_mtok_out REAL NOT NULL,
  au_per_mtok_cache_read REAL NOT NULL,
  au_per_mtok_cache_write REAL NOT NULL,
  usd_per_mtok_in REAL NOT NULL,   -- list price, for the notional column
  usd_per_mtok_out REAL NOT NULL,
  effective_from TEXT NOT NULL
);

CREATE TABLE allowance_pool (
  pool TEXT PRIMARY KEY,
  window TEXT NOT NULL,            -- '5h'|'weekly'
  capacity_au REAL NOT NULL,       -- calibrated, not published
  calibrated_at TEXT, calibration_r2 REAL
);

-- Observed ground truth. The only hard data we get about the ceiling.
CREATE TABLE limit_event (
  id INTEGER PRIMARY KEY,
  pool TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  window TEXT NOT NULL,
  source TEXT NOT NULL,            -- 'api_error'|'otel'|'manual'
  au_consumed_in_window REAL       -- our estimate at the moment it fired
);
```

**How capacity gets calibrated.** Published allowances are not exposed as a
number we can read, so `capacity_au` is fitted: every `limit_event` is an
observation that consumption in that window reached the ceiling. With a handful
of events the estimate converges well enough for a percentage to be meaningful.
Until then the dashboard shows allowance **share of period total** rather than
share of ceiling, and says so.

Whether consumption is exposed programmatically at all is a **Phase 0 question**
(§14). If it is, we read it and skip the modelling.

### 6.3 Notes on the model

- **`work_unit` is the unit of analysis, not the session.** A session spans
  hours and a dozen unrelated tasks; classifying at session level produces mush.
- **Consumption is always computed, never captured.** Storing tokens and
  recomputing against a versioned registry means a correction re-values history
  instead of corrupting it. This applies to both `allowance_units` and
  `list_value_usd`.
- **`allowance_pool` is not optional and never sums.** Anthropic seat allowance
  and OpenAI allowance are separate ceilings. Any query that adds them is a bug,
  and the dashboard must make that structurally impossible rather than a
  convention people remember.
- **Tier is resolved, not hardcoded.** `claude-opus-4-7@20250514` and
  `claude-opus-4-7` resolve to the same tier; `gpt-5-codex` resolves in the same
  registry. Fail loudly on an unmatched model rather than defaulting silently.
- **`department` is deliberately absent.** For v1 it is a view-level constant.
  Multi-user makes it a join on the OTel `user.id`/`user.email` attributes.
  Designing it now would be speculative; leaving the join key available is free.

---

## 7. Classification taxonomy

Three orthogonal axes plus a stakes flag. Kept deliberately small — a small
local model's accuracy degrades sharply as the label set grows, and every label
we add has to earn its place by changing a decision.

### 7.1 `work_type` — 4 values

The *cognitive shape* of the work. This is the axis that most determines which
model tier is appropriate.

| Value | Definition |
|---|---|
| `Retrieval` | Find, read, summarise, answer from existing material. Little inference. |
| `Synthesis` | Combine and produce prose or a plan. Judgement, but bounded. |
| `Reasoning` | Diagnose, design, prove, trade off. Depth over breadth. Failure is subtle. |
| `Agentic` | Multi-step execution with tools against real state. Breadth, persistence, error recovery. |

### 7.2 `ai_activity` — the domain label

Open-ish enum, seeded from the reference report and extensible:

`debugging`, `feature-development`, `testing`, `refactoring`, `code-review`,
`architecture-design`, `security-review`, `incident-response`, `data-analysis`,
`pipeline-analysis`, `automation`, `documentation`, `dependency-management`,
`product-planning`, `requirements-gathering`, `roadmap-planning`, `onboarding`,
`research`, `other`

Rules: the enum is passed to the classifier *both* in the prompt and as a
structural constraint. `other` is always available — a forced choice into a
wrong label is worse than an honest `other`. If `other` exceeds 10% of volume,
the taxonomy needs a new label; that is a monthly review item, not an
auto-expansion.

### 7.3 `task_complexity` — 3 values

`Low` / `Medium` / `High`. **Three, not ten.**

Small models are meaningfully worse at ordinal regression than at categorical
labelling; a 1–10 scale invites false precision and inter-run instability. Three
buckets with explicit anchors in the prompt are both more stable and sufficient
for the decision this feeds.

Anchors:
- **Low** — single-step, well-specified, verifiable by inspection. Rename a
  variable. Summarise a file. Format a table.
- **Medium** — several steps, some ambiguity, one non-trivial decision. Add an
  endpoint following an existing pattern. Track down a shallow bug.
- **High** — genuine ambiguity, cross-cutting change, novel design, or a
  failure mode that is expensive to get wrong. Design a schema. Diagnose a race
  condition. Plan a migration.

### 7.4 `stakes` — 2 values

`routine` / `high`. Orthogonal to complexity: a *simple* change to auth config
is low complexity and high stakes. Drives the `Acceptable (high stakes)` verdict.

Heuristic seeds (classifier confirms): security-review, incident-response,
anything touching auth/secrets/payments, production config, database migrations,
CI/CD pipeline definitions, deploy scripts.

---

## 8. Verdict engine — `model_justification`

This is the core intellectual property of the system and the one part that
**must not be done by a model.** The verdict is a deterministic, auditable,
config-driven function. If it is not reproducible, nobody will act on it.

### 8.1 Expected tier

```
expected_tier = TIER_MATRIX[work_type][task_complexity]
if stakes == 'high': expected_tier = min(frontier, expected_tier + 1)
```

Default `TIER_MATRIX`. **This matrix was reverse-engineered from the reference
report** (§2) and then verified: the rules below reproduce the
`model_justification` value on all 28 visible rows of that report exactly. It is
still a hypothesis to be calibrated against our own outcome data (§16 Q2), but
it is a grounded one rather than a guess.

| work_type ↓ / complexity → | Low | Medium | High |
|---|---|---|---|
| **Retrieval** | small | small | mid |
| **Synthesis** | small | mid | mid ⚠ |
| **Agentic** | small | small | frontier |
| **Reasoning** | small | small | frontier |

⚠ `Synthesis / High` is the one cell with no supporting evidence in the
reference report — no such row appears. Set to `mid` on the reasoning that
synthesis is bounded judgement, and flagged for calibration.

Two cells are worth noting because they are counter-intuitive and fell out of
the data rather than from intuition: **`Agentic / Medium` and `Reasoning /
Medium` both expect `small`, not `mid`.** The implied claim is that
medium-complexity agentic execution is mechanical enough that a cheap model with
good tools handles it — which, if true, is where most of the reclaimable headroom
lives, since that is also where most of the volume sits.

### 8.2 Verdict function

`tier_delta = used_tier − expected_tier`, on the ordinal scale
`small=0, mid=1, frontier=2`.

| Condition | Verdict |
|---|---|
| ≥ 2 under-provisioning signals fired (§8.3) | **Underprovisioned** *(overrides all below)* |
| `tier_delta ≥ +2`, or `+1` when `complexity == Low` | **Overprovisioned** |
| `tier_delta == +1` (Medium/High) | **Acceptable** |
| `tier_delta == 0` | **Justified** |
| `tier_delta ≤ −1` and `stakes == routine` | **Acceptable** *(downgrade candidate — it worked)* |
| `tier_delta ≤ −1` and `stakes == high` | **Acceptable (high stakes)** *(review)* |

Note the asymmetry, which is intentional: this is a **cost lens**, not a
symmetric fit score. `Justified` means "you picked exactly the right tier."
`Acceptable` means "you did not overspend" — which covers both a mild overshoot
and a successful downgrade. `Overprovisioned` means "you spent money you didn't
need to." And `Underprovisioned` overrides everything, because a cheap model
that burns forty minutes of engineer time is the most expensive outcome in the
table and the one a pure cost view will never surface.

**Verified.** A reference implementation of §8.1 + §8.2 (`verify_rules.py`,
shipped alongside this document) reproduces the `model_justification` value on
**28 of 28** rows of the reference report. The matrix and the rules are therefore
not a plausible-sounding invention — they are the actual decision function behind
the target artifact, recovered and made explicit.

The `Acceptable (high stakes)` verdict is not a cost finding at all — it is a
risk flag. It marks work where a below-expected tier was used on something
expensive to get wrong, and it belongs in a review queue rather than a savings
ledger.

### 8.3 Under-provisioning signals

This is the part no existing tool does, and it is entirely deterministic —
derived from `outcome_signal`, not from a model's opinion. A signal fires when
the metric exceeds the **p75 for that (`ai_activity`, `work_type`) cohort**,
so the thresholds self-calibrate rather than being guessed:

| Signal | Fires when |
|---|---|
| `turn_excess` | turns > cohort p75 × 1.5 |
| `tool_error_rate` | > cohort p75 |
| `edit_thrash` | same file edited ≥ 4 times in one work unit |
| `model_escalated` | a `PreModelSwitch` to a higher tier occurred mid-unit |
| `corrective_turns` | ≥ 2 user messages matching correction patterns |
| `prompt_restated` | user re-asked a semantically near-identical request |
| `abandoned` | unit ended on interruption without a completed edit/commit |

Two or more fired signals ⇒ `Underprovisioned`, with the fired set written into
`verdict.evidence` so the row is defensible when someone challenges it.

### 8.4 Impact — headroom, not dollars

For `Overprovisioned` rows:

```
headroom_reclaimable = allowance_units_consumed
                     − (tokens re-priced at expected_tier allowance weight)
headroom_pool        = the pool the used model drew from
```

Reported as **points of the pool's period allowance**, e.g. *"reclaims 6.2 points
of the weekly Anthropic allowance."* The notional dollar equivalent may be shown
alongside, greyed and labelled, for ranking and for conversations with Finance.

This is a better number than v0.1's `est_savings_usd` in two ways:

- **It is verifiable.** A dollar saving on a seat plan never appears on any
  invoice, so the claim can never be checked and the dashboard's credibility
  slowly rots. A headroom claim can be checked the following week by watching
  whether `limit_event` rows stop appearing.
- **It is still an upper bound, and must be labelled as one.** It assumes the
  cheaper model completes the work in the same number of tokens. It will not.
  Treat as a ranking signal for where to look, never as a forecast. A dashboard
  that promises "8.3 points reclaimable" and delivers 3 destroys the credibility
  of everything else on the page.

### 8.5 Verdicts are per-pool, and one move is not a verdict at all

Every verdict is scoped to the pool the model drew from. `Overprovisioned` means
*"scarce headroom in **this** pool was spent on work a cheaper tier in **this**
pool would have handled."*

That leaves one important move the verdict engine deliberately does **not**
score: **moving work between pools.** Delegating a task from Claude Code to a
Codex subagent does not reduce consumption — it transfers it to a different
ceiling. Whether that is good depends entirely on which ceiling is binding, and
that is a question about the week, not about the task. It belongs in an analysis
(§10 A6), not in a per-unit verdict, and conflating the two would produce
confident nonsense.

---

## 9. The local classifier

### 9.1 Model selection

**Recommendation: `qwen3:4b` via Ollama (~2.5 GB on disk, 256K context).**
Fallback if memory pressure bites: `qwen3:1.7b` (~1.4 GB).

Rationale, from the zero-shot classification evidence available: the Qwen3
family is a strong outlier at small scale on exactly this kind of task —
Qwen3-4B scores materially above Llama-3.2-3B and Phi-4-mini at comparable
size, and is within noise of Qwen3-8B. Going bigger than 4B buys almost nothing
for coarse labelling, which means our 8 GB ceiling costs us far less accuracy
than it first appears. Below ~1.7B there is a cliff, not a slope — sub-1B models
are not usable here.

Explicitly rejected:
- **Gemma 4** (`e2b` is 7.2 GB on disk despite the name) — does not fit.
- **MLX / `mlx-lm`** — the honest decode advantage is ~1.4–1.8×, but MLX's
  weakness is *prefill*, and our workload is prefill-dominated (long transcript
  excerpt in, ~30 tokens of JSON out). It may well be slower for us. Also note
  Ollama's own MLX backend reportedly only activates at ≥32 GB unified memory
  and falls back silently below that. Not worth the complexity; revisit only
  with a measurement.
- **Hosted Haiku** — would give better labels, but the entire point is that this
  system costs nothing to run and never sends prompt content off the machine.
  Reserved for gold-set generation only (§9.5).

**Verify the actual quantisation before trusting the size.** Ollama tags are not
uniformly Q4 — some default to Q8_0. Run `ollama show` and pull an explicit
`-q4_K_M` tag if needed.

### 9.2 Execution model — batch, never inline

Classification runs as a **nightly batch job** (`launchd` at 02:00, plus manual
trigger), not in a hook and not in the request path.

This is the single most important operational decision in the PRD, and it
follows directly from the 8 GB constraint. Inline classification would put a
2.5 GB model in memory alongside the IDE, the browser and Claude Code, on a
machine that cannot afford it — degrading the very workflow we are trying to
optimise. Running at 02:00, the model has the machine to itself, `OLLAMA_KEEP_ALIVE`
keeps it warm across the batch, and nobody is waiting.

The cost of this choice is report freshness of up to 24 hours, which for a
weekly right-sizing loop is irrelevant.

Throughput sanity check: at an estimated 25–32 tok/s decode for a 4B on an M3,
and ~30 output tokens per classification, decode is well under a second per unit.
Prefill of a ~2k-token excerpt dominates. A heavy day of 300 work units should
complete in well under 30 minutes. If it does not, the excerpt is too long —
tighten §9.4 before reaching for a smaller model.

### 9.3 Structured output

Use Ollama's `format` parameter with an explicit JSON schema. Ollama compiles
the schema to a GBNF grammar and constrains sampling, so **output is
structurally guaranteed valid** regardless of model size. Constraining
`ai_activity` and `work_type` to literal enums in the schema makes an invalid
label impossible.

```json
{
  "type": "object",
  "required": ["ai_activity","work_type","task_complexity","stakes","confidence","rationale"],
  "properties": {
    "ai_activity":     {"type":"string","enum":["debugging","feature-development", "..."]},
    "work_type":       {"type":"string","enum":["Retrieval","Synthesis","Reasoning","Agentic"]},
    "task_complexity": {"type":"string","enum":["Low","Medium","High"]},
    "stakes":          {"type":"string","enum":["routine","high"]},
    "confidence":      {"type":"number"},
    "rationale":       {"type":"string","maxLength":160}
  }
}
```

> **Critical implementation detail.** Ollama does *not* inject the schema into
> the prompt — the model never sees it. Grammar constraint alone yields
> structurally valid JSON with semantically garbage values. **The schema, the
> full enum lists, and the complexity anchors must all be restated in the prompt
> text.** This is the single biggest failure mode for a small classifier and the
> most likely cause of a disappointing v1.

Also: `temperature: 0`, flat schema (nested grammars slow sampling measurably),
`num_ctx` capped to what the excerpt actually needs.

### 9.4 What the classifier is shown

Not the whole work unit — that would be expensive and would bury the signal.
A deterministic **excerpt builder** produces a compact, structured summary,
targeting ~1,500 tokens:

1. The user's opening prompt, verbatim, truncated to 600 tokens.
2. A tool-call histogram: `Read×12, Edit×4, Bash×3, Grep×7`.
3. Normalised targets: file extensions touched, up to 8 distinct paths (basenames
   only), bash command *verbs* only (`pytest`, `git`, `npm`) — never full commands.
4. The repo name and branch.
5. First and last 200 tokens of the assistant's final message.
6. Deterministic counters: turns, errors, duration.

Two benefits beyond cost: it is **stable** (same input → same excerpt → cacheable),
and it strips most incidental secrets before anything reaches the model. Since
the model is local, that is defence in depth rather than a hard requirement, but
it also means the excerpt can safely be sent to a hosted model for gold-set
generation.

**Caching:** key on `hash(excerpt + classifier_version)`. Repetitive work
produces identical excerpts; expect a meaningful hit rate and near-zero
marginal cost for re-runs.

### 9.5 Calibration and quality control

Not optional. An uncalibrated classifier produces a report nobody trusts, and an
untrusted report gets ignored — the most likely failure mode for this project is
not that it breaks, but that it works and nobody believes it.

- **Gold set.** Hand-label 200 work units sampled stratified across activity and
  consumption decile. This is a day of work and it is the highest-leverage day in the
  project.
- **Agreement target.** ≥ 80% on `work_type` and `task_complexity`. Report the
  confusion matrix, not just accuracy — a classifier that systematically reads
  `Agentic` as `Reasoning` breaks the tier matrix in a specific, correctable way.
- **Second-opinion sampling.** Send 5% of excerpts to a hosted small model and
  measure disagreement as a drift alarm. Costs cents per month.
- **Self-consistency.** Re-run 20 units three times; label instability above 10%
  means the prompt anchors are too weak.
- **Confidence gating.** Rows below a confidence threshold are excluded from
  headline verdicts and routed to a review queue rather than silently trusted.

---

## 10. Analyses

The dashboard is a means, not the end. Six analyses justify the build.

### A1 — Over-provisioning ledger *(the reference report)*
Consumption grouped by activity × work type × complexity × model, with verdict.
Sorted by `headroom_reclaimable` descending, per pool.
**Action:** change the default model for a class of work, or add a routing rule.

### A2 — Under-provisioning ledger
Work units flagged `Underprovisioned`, with the fired signals and estimated
wasted wall-clock. Sorted by `turns × duration`.
**Action:** raise the default tier for that activity, or fix the prompt or
context that caused the thrash.

*Bootstrapped from escalation events.* Every `PreModelSwitch` upward is a
human-labelled example of under-provisioning (§5.1 Source C). Those labels come
free, need no classifier, and are what the cohort thresholds get calibrated
against. This is the analysis most likely to produce a genuinely surprising
finding, and on a seat plan it is also the most valuable: wasted engineer time
is a real cost in a way that notional token spend is not.

### A3 — Subagent candidates *(G3)*
Cluster work units by embedding of the excerpt (`nomic-embed-text` via Ollama,
~274 MB — fits alongside the classifier if run sequentially), then rank by:

```
score = frequency × mean_allowance_units
        × (1 − mean_complexity_ordinal) × tool_signature_coherence
```

Frequent, expensive, low-complexity, narrow consistent tool set is a textbook
subagent candidate. Output per candidate: proposed name, observed tool
allowlist, recommended tier, historical consumption, and 5 example prompts to
seed the description.

### A4 — Context efficiency
Independent of model choice and often the larger lever. Cache hit rate by repo
and session shape; consumption of loaded-but-unused skills and MCP tool schemas
(needs `OTEL_LOG_RAW_API_BODIES`); compaction frequency; ratio of
`cache_creation` to `cache_read`.
**Action:** trim CLAUDE.md, lazy-load skills, restructure sessions.

*Note:* prompt-cache efficiency is pure headroom. A cache miss consumes full
input allowance for context that was already paid for once — which on a seat
plan is directly the reason someone hits the wall on Thursday.

### A5 — Frustration map *(Phase 3, see §11)*
Frustration rate by `agent_type` and `ai_activity`.

### A6 — Pool balance *(new)*
Consumption against each pool's ceiling, side by side, with limit-hit events
marked. Which pool is actually binding, and by how much.

This is the analysis that makes the Codex delegation legible. If the Anthropic
seat allowance is the constraint and the OpenAI pool has slack, then delegating
suitable work to Codex is not overspending — it is the correct move, and the
tool should say so. If both pools are near their ceilings, delegation buys
nothing and the answer is right-sizing instead.

**Action:** shift a class of work between agents, or conclude that delegation
is not the lever this week. Explicitly *not* a per-unit verdict (§8.5).

---

## 11. Phase 3 — Frustration and sentiment

Deliberately last, because it depends on subagent attribution being correct and
on having enough history for baselines to mean anything.

**Signals are behavioural first, lexical second.** Behaviour is harder to fake
and does not require reading anyone's tone:

| Behavioural | Lexical *(local model)* |
|---|---|
| User interrupted mid-generation (`Stop`) | Explicit negation openers ("no,", "that's not", "still") |
| Prompt restated with high semantic similarity | Escalating imperatives, all-caps, repeated punctuation |
| ≥ 3 corrective turns in one unit | Directives to stop or start over |
| Session abandoned without completion | Profanity |
| Model escalated mid-unit | |

Score 0–3 per work unit, aggregated by `agent_type` and `ai_activity`.

**Guardrails, stated explicitly because this is the part that could go wrong:**

- Single-operator scope means this is self-observation, not surveillance. **If
  and when this goes multi-user, frustration analysis must be opt-in and
  reported only in aggregate.** It must never become an input to anyone's
  performance review. Write this into the tool's README before it can be
  misread.
- Frustration is a **property of the agent design, not the person.** The report
  headline is "the `test-writer` subagent produces 3× the frustration rate of
  baseline," never anything about who was typing.
- Lexical scoring runs on user messages only, locally, and the raw text is never
  persisted alongside the score — only the score and the fired signal set.

---

## 12. Dashboard

Local-only, `localhost`, no auth (single operator, single machine).
FastAPI + a single-page frontend, or Streamlit if speed of build matters more
than polish. **Do not build an SPA framework app for this.**

Views:

1. **Model Use Index** — the reference table. Filterable on every dimension,
   sortable, every row drills through to its constituent work units and from
   there to the raw transcript excerpt.
2. **Allowance over time** — per pool, by model tier and by verdict, with
   `limit_event` markers overlaid. A config change should show as a step in the
   chart and, better, as limit-hit events stopping. This is how the system
   proves it paid for itself.
3. **Under-provisioning queue** — A2, as a worklist.
4. **Subagent candidates** — A3, each card actionable.
5. **Pool balance** — A6. Each pool against its ceiling, side by side. The one
   view where the Codex delegation question is answerable.
6. **Data quality** — coverage %, single-source records, reconciliation delta,
   orphaned delegations, allowance-model fit quality,
   parse-degraded rate, `other` label rate, classifier confidence distribution.
   *This view exists so that trust in the numbers is itself observable.*

Plus a raw SQL console, because the interesting question is always the one the
dashboard doesn't have a view for.

---

## 13. Non-functional requirements

| | Requirement |
|---|---|
| **Latency** | Zero added latency to interactive turns. Hooks < 50 ms, non-blocking, `exit 0` unconditionally. |
| **Resource** | Ingest + dashboard < 200 MB RSS. Classifier batch may use up to 4 GB but only outside working hours. |
| **Durability** | SQLite WAL. Nightly backup of the DB file. Raw events reconstructible from transcripts on disk. |
| **Privacy** | No prompt content leaves the machine. Excerpts strip full bash commands and full file paths. No telemetry from this tool itself. |
| **Security** | Telemetry env vars set in shell profile, outside any repo. OTLP endpoint bound to `127.0.0.1`. If Source C is enabled: pinned Docker image, ≥ 1.83.0, never a bare `pip install`. |
| **Failure isolation** | Every component fails safe. If the classifier is down, rows stay unclassified and the report degrades. If the tailer is down, the transcript files are still on disk and can be backfilled. Nothing in this system may ever break Claude Code. |
| **Reproducibility** | Every derived number is reproducible from raw events plus the versioned model registry, allowance model, taxonomy, and rules config. |

---

## 14. Delivery plan

Sequenced so something useful exists after every phase, and so the riskiest
unknowns are resolved before anything is built on them.

### Phase 0 — Reconnaissance *(~1–2 days) — before writing any other code*

Pure investigation. Its entire purpose is to replace six assumptions with facts.

| Question | Method | Why it blocks |
|---|---|---|
| What does a subagent run look like on disk — inlined with `isSidechain`, or a separate file? | Spawn a known subagent, diff `~/.claude/projects/` | §5.4 — a wrong answer silently misattributes subagent consumption |
| **Where does Codex write session logs, and do they carry token counts?** | Run a Codex subagent, locate and inspect its records | §5.1 Source E — the whole cross-provider story depends on it |
| **Is allowance consumption exposed programmatically, or must it be modelled?** | Inspect OTel output, `/usage` internals, API error payloads on a limit hit | §6.2 — determines whether the primary measure is read or fitted |
| Does `OTEL_LOG_RAW_API_BODIES=1` work, and what does it emit? | Enable, run a session, inspect collector output | Determines whether A4 is possible at all |
| Do transcript token fields agree with OTel metrics? | Known workload, reconcile | §5.3 — which source is authoritative |
| Which hooks fire on this version, with what payload? | Register logging stubs for all candidates | §5.1 Source C, especially `PreModelSwitch` |

**Exit criteria:** a one-page findings memo with sample records for each, and a
go/no-go on the allowance model vs. direct read.

### Phase 1 — Capture and consumption *(~1–1.5 weeks)*
Transcript tailer, OTel collector, hooks, the `codex` wrapper, and the Codex log
tailer. Normalisation into `work_unit` / `api_call` / `delegated_call`. Model
registry and allowance model. Backfill all existing history.

**Ships:** accurate consumption by model, repo, session and pool — including
delegated work — with no classification yet. Already better than `/usage`.
**Acceptance:** Anthropic token totals reconcile with `/usage` within 2% over 7
days; ≥ 98% of Codex sessions join to a parent work unit.

### Phase 2 — Classification and verdicts *(~1 week)*
Ollama + `qwen3:4b`, excerpt builder, batch runner, gold set, calibration.
Outcome-signal extractor. Verdict engine. The Model Use Index view.

**Ships:** the reference report, in headroom terms. G1, G2, G6 met.
**Acceptance:** ≥ 80% gold-set agreement; `other` rate < 10%; at least one
over-provisioning finding the operator agrees with.

### Phase 3 — Analyses *(~1 week)*
Under-provisioning ledger bootstrapped from escalation events, subagent
clustering, context efficiency, pool balance, full dashboard.

**Ships:** G3 met. At least three concrete right-sizing actions.
**Acceptance:** one recommended action implemented, and the resulting change
visible in the allowance time-series — ideally as limit-hit events stopping.

### Phase 4 — Conditional extensions
- **4a — OpenAI-side gateway** — only if Phase 0 shows the Codex logs
  insufficient. Far lower risk than an Anthropic-side proxy.
- **4b — Frustration analysis** — §11.
- **4c — Multi-user** — schema is ready; needs a central store, identity, and a
  privacy policy. A separate decision, not a rollout of this.
- **Anthropic-side gateway** — out of scope. §5.2.

---

## 15. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Delegated (Codex) consumption stays invisible or misjoins** | High | Phase 0 confirms the log format; the wrapper stamps the parent at the call site; orphaned delegations are surfaced, never dropped. If E1 fails, an OpenAI-side gateway is the fallback. |
| **Allowance capacity can't be observed and the model is wrong** | High | Fall back to share-of-period-total rather than share-of-ceiling, and say so on the page. Calibrate against `limit_event` rows as they accumulate; publish the fit quality in the data-quality view. |
| **Transcript schema drifts and ingestion silently degrades** | High | Defensive parser, 1% schema canary, version per record, OTel cross-check. Failure mode is graceful and re-ingestable. |
| **Classifier is mediocre and nobody trusts the report** | High | Gold set, published confusion matrix, confidence gating, visible data-quality view. Budget the full calibration day; do not skip it. |
| **Headroom estimates over-promise and credibility is lost** | High | Label as upper bound. Track predicted vs. realised after the first implemented action and publish the gap. |
| **Subagent attribution is wrong** | High | Phase 0 resolves it; hooks confirm independently |
| **Pools get summed somewhere** | Medium | Structural, not conventional: no query path in the dashboard can aggregate across `allowance_pool`. |
| **8 GB is genuinely too tight even for batch** | Medium | Fall back to `qwen3:1.7b`; tighten excerpts before shrinking the model further |
| **Built, then abandoned** | Medium | Phase 1 ships standalone value; each phase is independently useful. If it stalls after Phase 2, the report still exists. |
| **Scope creep into a product** | Medium | Non-goals in §3 are load-bearing. Internal tooling, one machine. |
| ~~Gateway breaks prompt caching~~ | — | Retired. No Anthropic-side gateway (§5.2). |
| ~~Subscription-auth ToS ambiguity~~ | — | Retired as a build risk for the same reason. Remains a reason not to revisit. |

---

## 16. Open questions

1. **Where does Codex keep its session records, and do they carry token
   accounting?** The single highest-priority Phase 0 item — G6 rests on it.
   *Blocks Phase 1.*
2. **Is allowance consumption readable, or must it be fitted?** If Claude Code
   exposes remaining allowance anywhere machine-readable, §6.2 collapses to a
   read and the primary measure becomes exact rather than modelled.
   *Blocks the headline number, not the build.*
3. **Is the tier matrix in §8.1 right?** It is a hypothesis, recovered from the
   reference report and reproducing it exactly, but not yet tested against our
   own outcomes. After Phase 2 there will be enough history: do
   `Acceptable (downgrade candidate)` rows actually show clean outcomes? If a
   tier assignment consistently produces under-provisioning signals, the matrix
   is wrong, not the run.
4. **How should delegation appear in the Model Use Index?** A delegated work
   unit has one classification and consumption in two pools. Current plan is one
   row with a `delegated_to` marker and per-pool consumption columns; the
   alternative is splitting into two rows. Decide once there is real data to
   look at.
5. **Should `work_unit` split on topic change within a prompt?** "Fix the tests
   and then refactor the parser" is two activities. v1 classifies to the
   dominant one; if the `other` rate or confidence suggests this is common,
   multi-label may be needed.
6. **Do we need per-repo tier matrices?** A prototype and a production service
   arguably warrant different defaults. Defer until there is evidence.

---

## 17. Appendix A — Sources

**Claude Code interfaces**
- [Monitoring & OpenTelemetry](https://code.claude.com/docs/en/monitoring-usage)
- [Hooks reference](https://code.claude.com/docs/en/hooks)
- [Manage sessions / transcript storage](https://code.claude.com/docs/en/sessions)
- [LLM gateway configuration](https://code.claude.com/docs/en/llm-gateway)
- [Gateway protocol reference](https://code.claude.com/docs/en/llm-gateway-protocol) — the authoritative contract for any `ANTHROPIC_BASE_URL` proxy
- [Manage costs](https://code.claude.com/docs/en/costs)
- [Headless / output formats](https://code.claude.com/docs/en/headless)

**Gateway**
- [LiteLLM Claude Code quickstart](https://docs.litellm.ai/docs/tutorials/claude_code_byok) · [custom callbacks](https://docs.litellm.ai/docs/observability/custom_callback) · [beta-header incident](https://docs.litellm.ai/blog/claude-code-beta-headers-incident) · [March 2026 security update](https://docs.litellm.ai/blog/security-update-march-2026)
- LiteLLM issues on unreliable body logging and zero-spend passthrough: [#15641](https://github.com/BerriAI/litellm/issues/15641), [#24204](https://github.com/BerriAI/litellm/issues/24204), [#22398](https://github.com/BerriAI/litellm/issues/22398)
- Supply-chain analysis: [OX Security](https://www.ox.security/blog/litellm-malware-malicious-pypi-versions-steal-cloud-and-crypto-credentials/) · [Sonatype](https://www.sonatype.com/blog/compromised-litellm-pypi-package-delivers-multi-stage-credential-stealer)
- [OTel header-helper exfiltration technique](https://bloom.security/blog/welcome-to-otel-claudeifornia)

**Delegated agents**
- Codex CLI session-record location and schema — **to be confirmed empirically**, Phase 0 item #2. No citation offered here on purpose: the research pass did not verify it.

**Local models**
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs) · [how the grammar constraint works](https://blog.danielclayton.co.uk/posts/ollama-structured-outputs/)
- [Qwen3](https://ollama.com/library/qwen3) · [Qwen3.5](https://ollama.com/library/qwen3.5)
- [BTZSC zero-shot classification benchmark, arXiv 2603.11991](https://arxiv.org/html/2603.11991) — basis for the Qwen3-4B recommendation
- [MLX vs llama.cpp analysis](https://www.promptquorum.com/local-llms/mlx-vs-ollama-vs-llama-cpp-mac)

---

## 18. Appendix B — Confidence in these findings

Written after a research pass, not after a build. Calibrating what to trust:

| Claim | Confidence | Note |
|---|---|---|
| Transcript path pattern and `message.usage` field names | High | Consistent across sources; schema *stability* is the risk, not existence |
| OTel metric/event names and attributes | High | Documented interface |
| Delegated Codex consumption is invisible to Sources A/B/C | High | Follows directly from those calls never reaching Anthropic's API |
| `qwen3:4b` is the right local classifier for 8 GB | High | Benchmark evidence is direct; size math unambiguous |
| Ollama structured output is grammar-constrained but the schema is never shown to the model | High | Confirmed in Ollama's docs; the most actionable single finding in the research |
| Seat plans make dollars notional and headroom the real currency | High | Follows from the billing model |
| Anthropic-side gateway is not worth it | High | Four independent reasons compounding (§5.2) |
| **Where Codex writes session logs, and what they contain** | **Low** | Not verified. Phase 0 item #2. |
| Subagent on-disk representation | **Low** | Sources conflicted. Phase 0 resolves. |
| `OTEL_LOG_RAW_API_BODIES=1` behaviour | **Low** | Reported but undocumented; truncation/redaction unverified |
| **Whether allowance consumption is machine-readable** | **Low** | Unverified either way. Determines read-vs-model. |
| **Per-token allowance weights** | **Low by design** | Fitted, not published. May track list price closely — in which case the value of the reframe is the fixed denominator and the pool split, not the weighting. |
| Throughput estimates on base M3 8 GB | Medium | Bandwidth-derived, cross-checked against M1 measurements; no direct benchmark for this config exists |
| The tier matrix in §8.1 | **Reproduced, not validated** | Recovered from the reference report and matching it 28/28 — but that proves fidelity to the source, not that the source was right |

---