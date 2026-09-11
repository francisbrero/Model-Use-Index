-- 003_views.sql — the Datasette surface.
--
-- Datasette is the Phase 1 UI (TD §8.1): point it at the file and get a
-- queryable, faceted UI plus a SQL console for zero code. Don't hand-build a
-- dashboard before Phase 3.
--
-- These views exist because the operator WILL write ad-hoc queries — that is
-- the point of Datasette — and the caveats this slice ships under must survive
-- a `SELECT *`. Prose on a page nobody built is not a delivery mechanism.

-- ---------------------------------------------------------------------------
-- Every caveat this slice ships under, as ROWS rather than prose.
--
-- A reader who sees no `Underprovisioned` verdicts and assumes they are rare
-- is being misled: the slice cannot emit one at all. PRD §8.2 makes that
-- verdict override everything, so its absence biases every number toward
-- over-provisioned. Same for headroom, and for the classification's status.
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_caveats AS
SELECT
  'no_headroom' AS caveat,
  'Every dollar figure is NOTIONAL LIST VALUE, not money billed' AS summary,
  'We are on seat subscriptions. The primary measure (share of a pool period '
  || 'allowance) needs the allowance model, which is deferred (U3/U3a). This '
  || 'slice emits no headroom figure at all — a documented temporary deviation '
  || 'from invariant 5, not a redefinition of it.' AS detail
UNION ALL SELECT
  'no_underprovisioned',
  'The verdict Underprovisioned is NEVER emitted by this slice',
  'PRD §8.3 derives it from outcome_signal and cohort p75 thresholds, neither '
  || 'of which this slice builds. Its absence is by construction, not because '
  || 'it is rare. Since §8.2 makes it override every other verdict, every '
  || 'number here is biased toward over-provisioned.'
UNION ALL SELECT
  'provisional_classification',
  'Every classification is PROVISIONAL and must not be acted on',
  'The classifier is an unvalidated deterministic heuristic until the gold set '
  || 'lands (M2-prime, R1). W1 showed two defensible heuristics over the same '
  || 'data disagreeing by three orders of magnitude, so a plausible number here '
  || 'is not a validated one.'
UNION ALL SELECT
  'work_type_partial',
  'Synthesis and Reasoning are never assigned',
  'work_type is set by deterministic rule, not observed: anchored arcs are '
  || 'Agentic. If most notional value lands in Agentic, the tier axis carried '
  || 'no information this round — check v_work_type_distribution before reading '
  || 'any verdict.'
UNION ALL SELECT
  'score_zero_gap',
  'The score-0 share does not reproduce W1''s 43.4% — it lands near 22%',
  'W1 read its six signals by hand; this is a coded reimplementation over a '
  || 'grown corpus and a privacy-scrubbed text reduction. The gap is REPORTED '
  || 'and the thresholds were NOT adjusted to close it — tuning until the '
  || 'headline reappears would fabricate it. Resolving the gap is what the '
  || 'gold set (M2-prime, R1) is for.'
UNION ALL SELECT
  'language_threshold_is_judgement',
  'Two of the six signals depend on a threshold nobody measured',
  'The debugging and self-correction signals fire when at least 25% of a '
  || 'unit turns carry the vocabulary. W1 read its units by hand and left no '
  || 'threshold to inherit, and the fire rate moves smoothly from 72% to 7% '
  || 'with no natural breakpoint. 25% was chosen so neither signal dominates '
  || 'the other four, which is a defensible reason rather than a measured one.'
UNION ALL SELECT
  'unscored_arcs',
  'Some arcs carry no prompt unit and are deliberately left unscored',
  'One prompt can open several arcs — the user asks once and the assistant '
  || 'invokes two skills — so an arc after the first may contain no prompt of '
  || 'its own. Those rows read task_complexity = Unscored and get NO verdict. '
  || 'Scoring them 0 would read as Agentic/Low, which against Opus produces '
  || 'Overprovisioned out of missing evidence. See v_unscored_arcs.'
UNION ALL SELECT
  'upper_bound',
  'Any reclaimable figure is an UPPER BOUND by construction',
  'It assumes the cheaper model finishes the work in the same number of tokens. '
  || 'It will not (R2).';

-- ---------------------------------------------------------------------------
-- Value per prompt unit. A VIEW, not a stored column.
--
-- `work_unit` is the sole cost-bearing grain. Two tables that each sum to the
-- whole corpus is a 2x double-count waiting for an ad-hoc join — this
-- project's own signature failure (invariant 10) one layer up. So prompt-grain
-- value is computed in exactly one place, here, by grouping the same
-- `api_call` rows a different way.
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_prompt_unit_value AS
SELECT
  p.id                AS prompt_unit_id,
  p.session_id,
  p.work_unit_id,
  p.repo,
  p.turns,
  a.allowance_pool,
  SUM(a.notional_list_value_usd) AS notional_list_value_usd,
  COUNT(*)            AS api_calls
FROM prompt_unit p
JOIN api_call a ON a.prompt_unit_id = p.id
GROUP BY p.id, a.allowance_pool;

-- ---------------------------------------------------------------------------
-- A1, at the level PRD §7.0 says a report must lead with: `ai_activity`.
--
-- The report's job is to surface CATEGORIES, not individual fixes. A named
-- release routine is one instance of "agentic ops on Opus", and the harness
-- change is made at that level. A view that ranked individual work units would
-- make the reader do the grouping — the shape W1 explicitly rejected.
--
-- Grouped by allowance_pool because pools never sum (invariant 4).
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_activity_ledger AS
SELECT
  c.ai_activity,
  w.allowance_pool,
  c.work_type,
  c.task_complexity,
  v.used_tier,
  v.justification,
  COUNT(DISTINCT w.id)               AS work_units,
  SUM(w.notional_list_value_usd)     AS notional_list_value_usd,
  'provisional'                      AS classification_status
FROM work_unit w
JOIN classification c
  ON c.unit_id = w.id AND c.unit_grain = 'work_unit'
LEFT JOIN verdict v
  ON v.work_unit_id = w.id
GROUP BY c.ai_activity, w.allowance_pool, c.work_type,
         c.task_complexity, v.used_tier, v.justification;

-- The `other` share is a first-class number, not a footnote: with ai_activity
-- as the reporting top level, an over-used `other` degrades the whole report
-- rather than one column. PRD §7.2 sets 10% as the monthly review trigger.
CREATE VIEW IF NOT EXISTS v_activity_other_share AS
SELECT
  w.allowance_pool,
  SUM(CASE WHEN c.ai_activity = 'other'
           THEN w.notional_list_value_usd ELSE 0 END)     AS other_notional_list_value_usd,
  SUM(w.notional_list_value_usd)                          AS total_notional_list_value_usd,
  ROUND(100.0 * SUM(CASE WHEN c.ai_activity = 'other'
           THEN w.notional_list_value_usd ELSE 0 END)
        / NULLIF(SUM(w.notional_list_value_usd), 0), 1)   AS other_pct,
  10.0                                                    AS review_threshold_pct
FROM work_unit w
JOIN classification c ON c.unit_id = w.id AND c.unit_grain = 'work_unit'
GROUP BY w.allowance_pool;

-- If most notional value is `Agentic`, the tier axis carried no information
-- this round, and every verdict below it should be read in that light.
CREATE VIEW IF NOT EXISTS v_work_type_distribution AS
SELECT
  c.work_type,
  c.provenance,
  w.allowance_pool,
  COUNT(*)                       AS work_units,
  SUM(w.notional_list_value_usd) AS notional_list_value_usd
FROM work_unit w
JOIN classification c ON c.unit_id = w.id AND c.unit_grain = 'work_unit'
GROUP BY c.work_type, c.provenance, w.allowance_pool;

-- The unattributable remainder — 7.4% of Opus notional value at full scale.
-- A LABELLED ROW, never silently dropped (U10).
CREATE VIEW IF NOT EXISTS v_unattributable AS
SELECT
  w.session_id,
  w.allowance_pool,
  w.turns,
  w.notional_list_value_usd,
  'work before a session first anchor, or a session with no anchor at all'
    AS why
FROM work_unit w
WHERE w.kind = 'unattributable';

-- Routine ledger: the drill-down beneath the activity ledger, never the top
-- level. `attributionSkill` is an ANCHOR, not a cost attributor — these
-- figures span each anchor's whole arc, not its tagged turns (invariant 11).
CREATE VIEW IF NOT EXISTS v_routine_ledger AS
SELECT
  w.anchor_skill                  AS routine,
  w.allowance_pool,
  COUNT(*)                        AS runs,
  SUM(w.notional_list_value_usd)  AS notional_list_value_usd,
  ROUND(AVG(w.notional_list_value_usd), 2) AS mean_per_run_notional_list_value_usd,
  SUM(w.turns)                    AS turns
FROM work_unit w
WHERE w.kind = 'arc'
GROUP BY w.anchor_skill, w.allowance_pool;

-- ---------------------------------------------------------------------------
-- Data quality — invariant 7's canary and invariant 10's, in one place.
--
-- This ships WITH the first view, not after it (R3): a tool that stopped
-- ingesting three weeks ago while still rendering a confident report is worse
-- than no tool. `mui doctor` is a later milestone; these are the numbers it
-- will read.
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_data_quality AS
SELECT
  (SELECT COUNT(*) FROM raw_event)                        AS raw_events,
  (SELECT COUNT(DISTINCT session_id) FROM raw_event)      AS sessions,
  (SELECT COUNT(*) FROM api_call)                         AS api_calls,
  (SELECT COUNT(*) FROM work_unit)                        AS work_units,
  (SELECT COUNT(*) FROM work_unit WHERE parse_degraded=1) AS degraded_work_units,
  -- Invariant 7's canary: records that did not parse at all on the last run.
  -- Alert if this crosses ~1% of raw_events — it means the transcript writer
  -- changed, and `cc_version` on api_call bisects it to a release.
  (SELECT parse_failures FROM normalize_run ORDER BY id DESC LIMIT 1)
      AS parse_failures_last_run,
  (SELECT unscored_arcs FROM normalize_run ORDER BY id DESC LIMIT 1)
      AS unscored_arcs_last_run,
  (SELECT ran_at FROM normalize_run ORDER BY id DESC LIMIT 1) AS last_normalize,
  (SELECT COUNT(*) FROM api_call WHERE work_unit_id IS NULL) AS orphaned_calls,
  (SELECT COUNT(*) FROM api_call WHERE error_kind IS NOT NULL) AS error_records,
  (SELECT COUNT(*) FROM api_call WHERE error_kind = 'rate_limit') AS limit_hits,
  (SELECT MAX(started_at) FROM api_call)                  AS last_api_call,
  (SELECT MAX(ingested_at) FROM raw_event)                AS last_ingest;

-- Arcs with no prompt unit to score them. A labelled row rather than a silent
-- absence: they hold real notional list value and must be visible in any
-- denominator, but they carry no verdict and none should be inferred.
CREATE VIEW IF NOT EXISTS v_unscored_arcs AS
SELECT
  w.id,
  w.session_id,
  w.anchor_skill,
  w.project_family,
  w.turns,
  w.allowance_pool,
  w.notional_list_value_usd,
  'no prompt unit covers this arc' AS why
FROM work_unit w
JOIN classification c
  ON c.unit_id = w.id AND c.unit_grain = 'work_unit'
WHERE c.task_complexity = 'Unscored';
