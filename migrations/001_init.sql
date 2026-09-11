-- 001_init.sql — Model Use Index, first E2E slice (M1, issue #14).
--
-- Raw SQL in numbered files applied against `schema_version`. No ORM, no
-- Alembic (CLAUDE.md invariant 8, TD §5): the schema is analytical and the
-- queries are the product.
--
-- DELIBERATELY ABSENT — the allowance model is out of scope for this slice
-- (U3/U3a deferred), so `allowance_units`, `headroom_reclaimable` and
-- `headroom_pool` do not exist here. A column filled with a placeholder is how
-- a headroom claim leaks into a slice that must emit none (invariant 5). They
-- arrive in `002_allowance.sql`; migrations are numbered and additive.
--
-- `allowance_pool` IS present and NOT NULL from day one. It is not a headroom
-- column — it is the grouping key that makes summing pools structurally
-- impossible (invariant 4).
--
-- Every USD column is named `notional_list_value_usd`, never `cost` or
-- `value_usd`, so a query author cannot drop the label by accident
-- (invariant 5). We are on seat subscriptions; no dollar figure here is money
-- anyone was billed.

CREATE TABLE IF NOT EXISTS schema_version (
  version     INTEGER PRIMARY KEY,
  applied_at  TEXT NOT NULL,
  name        TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Capture. Immutable: never updated, never deleted (invariant 2b).
--
-- The collector writes here and nowhere else, and understands nothing about
-- the payload beyond enough to find a session id (invariant 2). That is what
-- makes it unbreakable by a schema change, and why every parse failure is
-- recoverable by fixing `normalize/` and re-running over this table.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_event (
  id            INTEGER PRIMARY KEY,
  source        TEXT NOT NULL,            -- 'transcript' for this slice
  ingested_at   TEXT NOT NULL,
  session_id    TEXT,
  payload       TEXT NOT NULL,            -- the verbatim JSONL line
  content_hash  TEXT NOT NULL UNIQUE      -- makes backfill idempotent
);

-- Counters from the last derivation run. A canary that cannot fire must not
-- ship as a row: `v_data_quality` reads these, and without them its
-- parse-failure number would be a constant 0 reporting a permanently clean
-- bill of health — the exact failure `mui doctor` exists to prevent (R3).
CREATE TABLE IF NOT EXISTS normalize_run (
  id             INTEGER PRIMARY KEY,
  ran_at         TEXT NOT NULL,
  raw_events     INTEGER NOT NULL,
  parse_failures INTEGER NOT NULL,
  api_calls      INTEGER NOT NULL,
  work_units     INTEGER NOT NULL,
  prompt_units   INTEGER NOT NULL,
  unknown_models INTEGER NOT NULL,
  unscored_arcs  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS raw_event_session ON raw_event(session_id);
CREATE INDEX IF NOT EXISTS raw_event_source  ON raw_event(source);

-- ---------------------------------------------------------------------------
-- Registry. Rates are versioned data, never inline constants in an analysis
-- (token-accounting §2). Tier is resolved through here and fails loudly on an
-- unmatched model — a silent default would corrupt every `tier_delta`.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_registry (
  version                 TEXT NOT NULL,
  provider                TEXT NOT NULL,
  model_pattern           TEXT NOT NULL,   -- glob, matches version-pinned ids
  -- The ordinal scale PRD §8.2 does arithmetic on: small=0, mid=1, frontier=2.
  -- Constrained to exactly those three because `tier_delta` has no meaning
  -- outside them; a fourth value would either crash the verdict engine or, far
  -- worse, coerce to 0 and read as `Justified`.
  tier                    TEXT NOT NULL
      CHECK (tier IN ('small', 'mid', 'frontier')),
  -- `<synthetic>` is not a model. Claude Code writes it as `message.model` on
  -- rate-limit and error records, which carry no tokens. Those records must be
  -- kept (invariant 10b) and resolution fails loudly on unmatched models, so
  -- the registry has to hold a row for it — but it must never reach
  -- `used_tier`. This flag is that exclusion, kept out of the tier enum so the
  -- ordinal arithmetic stays total.
  is_billable             INTEGER NOT NULL DEFAULT 1,
  allowance_pool          TEXT NOT NULL,
  -- List prices, for the notional column only. All four fields are priced
  -- separately: cache traffic is ~93% of Opus notional value, and pricing
  -- cache_read at the input rate is a 10x error on the largest line item.
  usd_per_mtok_in         REAL NOT NULL,
  usd_per_mtok_out        REAL NOT NULL,
  usd_per_mtok_cache_write REAL NOT NULL,
  usd_per_mtok_cache_read  REAL NOT NULL,
  effective_from          TEXT NOT NULL,
  PRIMARY KEY (version, model_pattern)
);

-- ---------------------------------------------------------------------------
-- One row per unique API response, after invariant-10 dedup.
--
-- The duplicate records stay in `raw_event` untouched; this table is the
-- derivation. Dedup key is (message.id, requestId) with max per usage field —
-- not uuid, not the record, and not first-seen (which undercounts output,
-- because a partial streaming snapshot is written before the final count).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS api_call (
  id                       TEXT PRIMARY KEY,   -- message_id|request_id
  session_id               TEXT NOT NULL,
  work_unit_id             TEXT REFERENCES work_unit(id),
  prompt_unit_id           TEXT REFERENCES prompt_unit(id),
  message_id               TEXT,
  request_id               TEXT,
  provider                 TEXT NOT NULL,
  allowance_pool           TEXT NOT NULL,      -- never summed across (inv 4)
  model                    TEXT NOT NULL,      -- exact string, incl. <synthetic>
  model_tier               TEXT NOT NULL,
  input_tokens             INTEGER NOT NULL,
  output_tokens            INTEGER NOT NULL,
  cache_creation_tokens    INTEGER NOT NULL DEFAULT 0,
  cache_read_tokens        INTEGER NOT NULL DEFAULT 0,
  notional_list_value_usd  REAL NOT NULL,      -- NOT money anyone was billed
  registry_version         TEXT NOT NULL,
  attribution_skill        TEXT,               -- an anchor, not a cost attributor
  is_sidechain             INTEGER NOT NULL DEFAULT 0,
  -- A rate-limit hit is an assistant record with model '<synthetic>', all-zero
  -- usage, error 'rate_limit' and apiErrorStatus 429. It carries no tokens and
  -- must never be filtered out: it is the only on-disk evidence of an
  -- allowance boundary (invariant 10b).
  error_kind               TEXT,               -- enum: 'rate_limit'|'server_error'|...
  api_error_status         INTEGER,
  cc_version               TEXT,               -- drift bisects to a release
  turn_index               INTEGER NOT NULL,   -- position in (timestamp, message_id)
  started_at               TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS api_call_session   ON api_call(session_id);
CREATE INDEX IF NOT EXISTS api_call_work_unit ON api_call(work_unit_id);
CREATE INDEX IF NOT EXISTS api_call_prompt    ON api_call(prompt_unit_id);
CREATE INDEX IF NOT EXISTS api_call_pool      ON api_call(allowance_pool);
-- `v_data_quality` counts error and rate-limit records on every load. Without
-- this the view takes ~1.9s over a real corpus and Datasette's 1s SQL time
-- limit kills it — which would make the data-quality view the one page that
-- never renders, exactly the R3 failure it exists to catch.
CREATE INDEX IF NOT EXISTS api_call_error     ON api_call(error_kind);

-- ---------------------------------------------------------------------------
-- work_unit — the ARC grain, `u10-next-anchor-v1` (#13).
--
-- An anchor runs to the next anchor of any skill, else to session end. This
-- diverges from PRD §6.1's prompt grain deliberately: U10 measured the
-- alternatives and only this rule reproduces /release-prod without
-- double-counting. W1's anchor->session-end baseline double-counts $13,118 of
-- Opus notional list value.
--
-- `kind` carries the remainder rather than dropping it: work before a
-- session's first anchor, and sessions with no anchor at all, are 7.4% of Opus
-- notional value and must be a labelled row (U10).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS work_unit (
  id                       TEXT PRIMARY KEY,
  session_id               TEXT NOT NULL,
  kind                     TEXT NOT NULL
      CHECK (kind IN ('arc', 'unattributable')),
  rule_id                  TEXT NOT NULL,   -- 'u10-next-anchor-v1'
  anchor_skill             TEXT,            -- NULL for the remainder row
  start_turn               INTEGER NOT NULL,
  end_turn                 INTEGER NOT NULL,  -- inclusive
  turns                    INTEGER NOT NULL,
  started_at               TEXT,
  ended_at                 TEXT,
  cwd                      TEXT,
  -- Leaf directory name only — never a full path (invariant 6).
  repo                     TEXT,
  -- The worktree FAMILY: `Phoenix` covers Phoenix and every worktree cut from
  -- it (`phoenix1`, `website`, `webapp/worktrees/bug1`, ...). W1's "Phoenix and
  -- its worktrees are 73.4% of Opus value" is a statement about this column,
  -- not about `repo` — matching on the leaf name alone fragments the family
  -- across a dozen directory names and undercounts it badly.
  project_family           TEXT,
  git_branch               TEXT,
  cc_version               TEXT,
  allowance_pool           TEXT NOT NULL,
  notional_list_value_usd  REAL NOT NULL,
  -- Invariant 7: the transcript schema is undocumented and unstable, so a
  -- record that does not yield what the normaliser expects must be COUNTABLE
  -- rather than either silently dropped or fatal. A rising rate here is the
  -- schema-drift canary; `cc_version` on `api_call` bisects it to a release.
  parse_degraded           INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS work_unit_session ON work_unit(session_id);
CREATE INDEX IF NOT EXISTS work_unit_skill   ON work_unit(anchor_skill);

-- ---------------------------------------------------------------------------
-- prompt_unit — the PROMPT grain: one real user prompt and the work it caused.
--
-- This exists because W1's six complexity signals were calibrated at this
-- grain — 1,823 Phoenix units, of which 43.4% of notional value scored zero.
-- Thresholds like ">=5 distinct files" and ">=40 turns" mean something over a
-- prompt and nothing over an arc, which spans a median 69 turns after its tag
-- ends. Scoring arcs directly with prompt thresholds would put almost every
-- arc above zero and quietly destroy the headline.
--
-- So: signals score here, arcs aggregate from here, verdicts attach to arcs.
--
-- IT DELIBERATELY CARRIES NO DOLLAR COLUMN. `work_unit` is the sole
-- cost-bearing grain. Two tables that each sum to the whole corpus is a 2x
-- double-count waiting for an ad-hoc join — the project's own signature
-- failure (invariant 10) one layer up, and Datasette exists precisely so the
-- operator writes ad-hoc joins. Value per prompt unit comes from grouping
-- `api_call` by `prompt_unit_id`; see `v_prompt_unit_value` in 003.
--
-- BOUNDARY RULE `prompt-unit-v1`: a boundary is a `user` record that is not
-- `isMeta`, not `isSidechain`, and whose content holds no `tool_result` block.
-- That last clause is load-bearing and was measured, not assumed: 41,224 of
-- 44,680 Phoenix `user` records (92%) are tool results. Cutting at every `user`
-- record gives ~44k units against W1's 1,823 — off by 24x. The rule as stated
-- reproduces 1,918 Opus-bearing prompts against W1's 1,823, the 5% gap being
-- two days of corpus growth. Sidechain turns belong to the parent unit (U10).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prompt_unit (
  id             TEXT PRIMARY KEY,
  session_id     TEXT NOT NULL,
  -- The arc this unit STARTS in, for grouping only — not containment. A
  -- prompt unit can straddle an arc boundary, and when it does it is recorded
  -- against the arc of its first turn. That is harmless because cost lives on
  -- arcs and on `api_call`, never here; this FK exists so a reader can drill
  -- from a routine to the prompts inside it.
  work_unit_id   TEXT REFERENCES work_unit(id),
  rule_id        TEXT NOT NULL,                   -- 'prompt-unit-v1'
  start_turn     INTEGER NOT NULL,
  end_turn       INTEGER NOT NULL,
  turns          INTEGER NOT NULL,
  started_at     TEXT,
  ended_at       TEXT,
  repo           TEXT,
  project_family TEXT,
  allowance_pool TEXT NOT NULL,
  -- Two of W1's six complexity signals read the PROSE of a unit. The prose
  -- itself is never stored (invariant 6) — only the boolean outcome of
  -- matching a fixed vocabulary against it, from which no content can be
  -- reconstructed. Computed in `normalize/` and discarded there.
  has_debug_language     INTEGER NOT NULL DEFAULT 0,
  has_self_correction    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS prompt_unit_session   ON prompt_unit(session_id);
CREATE INDEX IF NOT EXISTS prompt_unit_work_unit ON prompt_unit(work_unit_id);

-- ---------------------------------------------------------------------------
-- tool_call — a normalize-layer derivation, and the input three of W1's six
-- signals need (">=5 distinct files", "repeated test runs") plus the `stakes`
-- heuristic (PRD §7.4).
--
-- `target` is NORMALISED ON THE WAY IN, never stored raw (invariant 6, G4):
-- a Bash call stores the command VERB only (`pytest`, `git`, `npm`) and never
-- the command body; a file path is reduced to a repo-relative directory and an
-- extension class, never an absolute path. Prompt content does not leave the
-- machine and does not land in this column either.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tool_call (
  id             TEXT PRIMARY KEY,
  session_id     TEXT NOT NULL,
  work_unit_id   TEXT REFERENCES work_unit(id),
  prompt_unit_id TEXT REFERENCES prompt_unit(id),
  tool_name      TEXT NOT NULL,
  target         TEXT,              -- verb or dir+ext class — never raw
  is_error       INTEGER NOT NULL DEFAULT 0,
  is_sidechain   INTEGER NOT NULL DEFAULT 0,
  turn_index     INTEGER NOT NULL,
  started_at     TEXT
);

CREATE INDEX IF NOT EXISTS tool_call_prompt_unit ON tool_call(prompt_unit_id);
CREATE INDEX IF NOT EXISTS tool_call_work_unit   ON tool_call(work_unit_id);

-- ---------------------------------------------------------------------------
-- Enrichment output. Separate table, keyed by version, because the taxonomy
-- WILL change and re-running enrichment over history must not lose it
-- (invariant 2b).
--
-- `classifier_version` for this slice literally contains the word
-- "provisional". The classifier is an unvalidated heuristic until the gold set
-- lands (M2', R1) and no figure from it is to be acted on.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS classification (
  unit_id            TEXT NOT NULL,
  unit_grain         TEXT NOT NULL,   -- 'work_unit'|'prompt_unit'
  classifier_version TEXT NOT NULL,
  -- PRD §7.2 — the REPORTING top level, and an open-ish enum by design: a
  -- forced choice into a wrong label is worse than an honest `other`. So it is
  -- deliberately NOT constrained here, which makes the reported `other` share
  -- its only guard (§7.2's 10% monthly review threshold).
  ai_activity        TEXT NOT NULL,
  -- PRD §7.1 — the TIER axis, and closed. These four values key TIER_MATRIX,
  -- and the 28/28 reference-report verification depends on them exactly, so a
  -- typo must be a write error rather than a row that silently never matches.
  work_type          TEXT NOT NULL
      CHECK (work_type IN ('Retrieval', 'Synthesis', 'Reasoning', 'Agentic')),
  -- How each axis was arrived at, per axis, because this slice assigns them by
  -- deterministic rule rather than observing them. `work_type` in particular
  -- collapses to 'Agentic' for anchored arcs, and TIER_MATRIX['Agentic'] is
  -- small/small/frontier — so if most value lands there, the tier axis carried
  -- no information this round and the reader has to be able to see that.
  provenance         TEXT NOT NULL,   -- JSON: {axis: 'rule'|'observed'|'model'}
  -- 'Unscored' is not a fourth complexity level; it is the ABSENCE of one.
  -- An arc no prompt unit covers has no evidence to score, and calling that
  -- `Low` would manufacture `Agentic/Low -> expects small -> Opus used ->
  -- Overprovisioned` out of missing data. It cannot key TIER_MATRIX, so no
  -- verdict is produced for such a row at all.
  task_complexity    TEXT NOT NULL
      CHECK (task_complexity IN ('Low', 'Medium', 'High', 'Unscored')),
  stakes             TEXT NOT NULL
      CHECK (stakes IN ('routine', 'high')),
  complexity_score   INTEGER,         -- W1's six signals, 0-6; NULL = unscored
  signals            TEXT,            -- JSON: which signals fired
  confidence         REAL NOT NULL,
  rationale          TEXT,
  classified_at      TEXT NOT NULL,
  PRIMARY KEY (unit_id, unit_grain, classifier_version)
);

-- ---------------------------------------------------------------------------
-- Verdicts. Deterministic, auditable, config-driven — the one part that must
-- not be done by a model (PRD §8). `verdict.py` is pure functions so these
-- rules stay unit-testable.
--
-- No headroom column here: see the header note.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS verdict (
  work_unit_id   TEXT NOT NULL REFERENCES work_unit(id),
  rules_version  TEXT NOT NULL,
  -- The six values of PRD §8.2 and no others.
  justification  TEXT NOT NULL
      CHECK (justification IN (
        'Justified', 'Acceptable', 'Acceptable (high stakes)',
        'Overprovisioned', 'Underprovisioned', 'Unclassified'
      )),
  expected_tier  TEXT NOT NULL CHECK (expected_tier IN ('small','mid','frontier')),
  -- An arc spans many API calls and this corpus is mixed-model (Opus main
  -- thread, Haiku sidechains). `used_tier` is the tier carrying the PLURALITY
  -- OF NOTIONAL LIST VALUE in the arc, not the max and not the modal call —
  -- max would let 40 cheap subagent calls be outvoted by one, and call-count
  -- would let them outvote the Opus work that dominates the value.
  -- `max_tier` is recorded alongside so a reader can see mixed arcs, and
  -- `mui verify` reports how often the two disagree.
  used_tier      TEXT NOT NULL CHECK (used_tier IN ('small','mid','frontier')),
  max_tier       TEXT CHECK (max_tier IN ('small','mid','frontier')),
  tier_delta     INTEGER NOT NULL,
  evidence       TEXT,            -- JSON: which signals fired
  -- Verdicts are per-pool and the pool is PART OF THE KEY (PRD §8.5). A
  -- verdict means "scarce headroom in THIS pool was spent on work a cheaper
  -- tier in THIS pool would have handled", so an arc spanning two pools has
  -- two verdicts and never one blended row. Keying without the pool would
  -- silently keep whichever was written last.
  allowance_pool TEXT NOT NULL,
  PRIMARY KEY (work_unit_id, rules_version, allowance_pool)
);
