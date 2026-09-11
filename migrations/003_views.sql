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
