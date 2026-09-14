-- 004_readable_views.sql — make the output legible.
--
-- The slice already produced correct numbers; this migration makes them
-- readable without a join the operator has to write. Two problems, both about
-- presentation rather than arithmetic:
--
--   1. A `verdict` row is a bare UUID, three tier strings and a JSON blob. It
--      is checkable but it does not say what happened or why.
--   2. A `work_unit` says which routine ran, and nothing about what it did.
--
-- Everything here is derived from data already captured and already
-- privacy-normalised (invariant 6): tool names, allowlisted command verbs,
-- hashed path classes, timestamps. No prompt text, no file names, no command
-- bodies — the summary describes the SHAPE of the work, never its content.
--
-- All figures remain NOTIONAL LIST VALUE; all classifications remain
-- PROVISIONAL (M2', R1).

-- ---------------------------------------------------------------------------
-- Per-work-unit shape, as structured columns. `v_work_unit_summary` composes
-- the readable line from these; they are split out so they stay sortable and
-- filterable in Datasette rather than trapped inside a string.
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_work_unit_shape AS
SELECT
  w.id,
  w.session_id,
  w.kind,
  w.anchor_skill,
  w.project_family,
  w.repo,
  w.git_branch_kind,
  w.turns,
  w.started_at,
  w.ended_at,
  -- Elapsed wall time. Deliberately NOT a measure of effort: U10 found single
  -- arcs containing gaps of six days, because a routine waiting on CI or on
  -- review is still the same arc. Read it as span, not as work.
  CAST(ROUND((julianday(w.ended_at) - julianday(w.started_at)) * 1440) AS INTEGER)
      AS elapsed_minutes,
  (SELECT COUNT(*) FROM tool_call t WHERE t.work_unit_id = w.id)
      AS tool_calls,
  (SELECT COUNT(*) FROM tool_call t
    WHERE t.work_unit_id = w.id AND t.tool_name = 'Bash')
      AS bash_calls,
  (SELECT COUNT(*) FROM tool_call t
    WHERE t.work_unit_id = w.id AND t.tool_name IN ('Edit','Write','NotebookEdit'))
      AS edit_calls,
  (SELECT COUNT(*) FROM tool_call t
    WHERE t.work_unit_id = w.id AND t.tool_name IN ('Task','Agent'))
      AS subagent_calls,
  -- Distinct path classes touched. These are hashed stems, so this counts
  -- files without naming any of them.
  (SELECT COUNT(DISTINCT t.target) FROM tool_call t
    WHERE t.work_unit_id = w.id AND t.target LIKE '%/%')
      AS distinct_files,
  (SELECT COUNT(*) FROM api_call a
    WHERE a.work_unit_id = w.id AND a.is_sidechain = 1)
      AS sidechain_calls,
  (SELECT COUNT(*) FROM api_call a
    WHERE a.work_unit_id = w.id AND a.error_kind = 'rate_limit')
      AS rate_limit_hits,
  (SELECT COUNT(DISTINCT a.model) FROM api_call a WHERE a.work_unit_id = w.id)
      AS distinct_models,
  w.allowance_pool,
  w.notional_list_value_usd
FROM work_unit w;

-- The three most-used Bash verbs per work unit, as one string. Verbs come from
-- the `command_verb` allowlist, so this is a vocabulary of about forty known
-- tokens and never an operator-specific name.
--
-- Capped at three deliberately. An uncapped GROUP_CONCAT produced lines like
-- `(grep/cat/sed/python3/pnpm/gh/ls/git/cp/find/mkdir/rm/node/jq)` — every verb
-- a long arc ever touched, which is noise rather than shape. The top three say
-- "this was a search-and-edit arc" or "this was a deploy arc"; the full
-- histogram is a `tool_call` query away when it is actually wanted.
CREATE VIEW IF NOT EXISTS v_work_unit_verbs AS
SELECT
  work_unit_id,
  GROUP_CONCAT(target, '/') AS top_verbs
FROM (
  SELECT work_unit_id, target, n,
         ROW_NUMBER() OVER (PARTITION BY work_unit_id ORDER BY n DESC, target)
             AS rank
  FROM (
    SELECT work_unit_id, target, COUNT(*) AS n
    FROM tool_call
    WHERE tool_name = 'Bash' AND target IS NOT NULL AND target <> 'other'
    GROUP BY work_unit_id, target
  )
)
WHERE rank <= 3
GROUP BY work_unit_id;

-- ---------------------------------------------------------------------------
-- The readable line. One row per work unit, scannable without a join.
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_work_unit_summary AS
SELECT
  s.id,
  COALESCE(s.anchor_skill, '(no routine)')  AS routine,
  c.ai_activity,
  c.task_complexity,
  v.justification,
  ROUND(s.notional_list_value_usd, 2)       AS notional_list_value_usd,

  -- A sentence a human can scan. Everything in it is shape, not content.
  CASE
    WHEN s.kind = 'unattributable'
      THEN 'unattributed work in this session'
    ELSE COALESCE(s.anchor_skill, 'untagged work')
  END
  || ' · '
  || CASE
       WHEN s.elapsed_minutes IS NULL       THEN 'unknown span'
       WHEN s.elapsed_minutes < 60          THEN s.elapsed_minutes || 'm'
       WHEN s.elapsed_minutes < 2880        THEN (s.elapsed_minutes / 60) || 'h'
       ELSE (s.elapsed_minutes / 1440) || 'd'
     END
  || ' · ' || s.turns || ' turns'
  || CASE WHEN s.bash_calls   > 0 THEN ' · ' || s.bash_calls || ' bash' ELSE '' END
  || CASE WHEN s.top_verbs IS NOT NULL THEN ' (' || s.top_verbs || ')' ELSE '' END
  || CASE WHEN s.edit_calls   > 0 THEN ' · ' || s.edit_calls || ' edits' ELSE '' END
  || CASE WHEN s.distinct_files > 0 THEN ' · ' || s.distinct_files || ' files' ELSE '' END
  || CASE WHEN s.subagent_calls > 0 THEN ' · ' || s.subagent_calls || ' subagents' ELSE '' END
  || CASE WHEN s.rate_limit_hits > 0 THEN ' · HIT LIMIT' ELSE '' END
      AS summary,

  s.project_family,
  s.git_branch_kind,
  s.elapsed_minutes,
  s.turns,
  s.tool_calls,
  s.distinct_files,
  s.subagent_calls,
  s.started_at,
  s.allowance_pool,
  'provisional'                              AS classification_status,
  'notional list value, not money billed'    AS value_label
FROM (
  SELECT sh.*, vb.top_verbs
  FROM v_work_unit_shape sh
  LEFT JOIN v_work_unit_verbs vb ON vb.work_unit_id = sh.id
) s
LEFT JOIN classification c
  ON c.unit_id = s.id AND c.unit_grain = 'work_unit'
LEFT JOIN verdict v
  ON v.work_unit_id = s.id AND v.allowance_pool = s.allowance_pool
ORDER BY s.notional_list_value_usd DESC;

-- ---------------------------------------------------------------------------
-- The verdict, in English.
--
-- A raw `verdict` row is a UUID, three tier strings, an integer and a JSON
-- blob. It is auditable but it does not say what happened, and a verdict
-- nobody can read is a verdict nobody acts on — which is the whole point of
-- the table.
--
-- `reasoning` states the actual rule that fired (PRD §8.2), so a row is
-- defensible without the reader having the PRD open. That matters most when
-- someone disagrees with a verdict: the answer should be in the row.
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_verdict_readable AS
SELECT
  COALESCE(w.anchor_skill, '(no routine)')       AS routine,
  c.ai_activity,
  v.justification                                AS verdict,
  s.summary                                      AS what_happened,

  -- Why this verdict, in the rule's own terms.
  CASE v.justification
    WHEN 'Overprovisioned' THEN
      'used ' || v.used_tier || ' where ' || c.work_type || '/'
      || c.task_complexity || ' expects ' || v.expected_tier
      || ' — ' || v.tier_delta || ' tier'
      || CASE WHEN v.tier_delta = 1 THEN '' ELSE 's' END || ' above'
    WHEN 'Justified' THEN
      'used ' || v.used_tier || ', which is exactly what ' || c.work_type || '/'
      || c.task_complexity || ' expects'
    WHEN 'Acceptable' THEN
      CASE WHEN v.tier_delta > 0
        THEN 'used ' || v.used_tier || ' against an expected ' || v.expected_tier
             || ' — a mild overshoot, not an overspend'
        ELSE 'used ' || v.used_tier || ' below the expected ' || v.expected_tier
             || ' and the work completed — a downgrade that worked'
      END
    WHEN 'Acceptable (high stakes)' THEN
      'used ' || v.used_tier || ' below the expected ' || v.expected_tier
      || ' on HIGH-STAKES work — a risk flag for review, not a saving'
    WHEN 'Underprovisioned' THEN
      'two or more under-provisioning signals fired'
    ELSE v.justification
  END                                            AS reasoning,

  -- What the complexity score was built from. The signals are the evidence a
  -- reader would challenge first, so they belong in the row rather than inside
  -- a JSON column.
  CASE
    WHEN c.task_complexity = 'Unscored'
      THEN 'no prompt unit covers this arc — deliberately unscored'
    WHEN c.signals IS NULL OR c.signals = '[]'
      THEN 'no complexity signal fired (score 0 of 6)'
    ELSE 'score ' || COALESCE(c.complexity_score, 0) || ' of 6: '
         || REPLACE(REPLACE(REPLACE(c.signals, '[', ''), ']', ''), '"', '')
  END                                            AS evidence,

  ROUND(w.notional_list_value_usd, 2)            AS notional_list_value_usd,
  v.expected_tier,
  v.used_tier,
  v.max_tier,
  v.tier_delta,
  w.project_family,
  w.turns,
  v.allowance_pool,
  w.started_at,
  v.rules_version,
  'provisional'                                  AS classification_status,
  'notional list value, not money billed'        AS value_label,
  'Underprovisioned is never emitted by this slice — see v_caveats'
                                                 AS known_gap,
  v.work_unit_id
FROM verdict v
JOIN work_unit w        ON w.id = v.work_unit_id
LEFT JOIN classification c
  ON c.unit_id = v.work_unit_id AND c.unit_grain = 'work_unit'
LEFT JOIN v_work_unit_summary s ON s.id = v.work_unit_id
ORDER BY w.notional_list_value_usd DESC;

-- ---------------------------------------------------------------------------
-- The one-screen answer: where did the allowance pool's value go, and how much
-- of it looks reclaimable. Grouped by pool because pools never sum
-- (invariant 4), and by `ai_activity` because that is the level a harness
-- default is actually set at (PRD §7.0).
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_summary AS
SELECT
  w.allowance_pool,
  c.ai_activity,
  COUNT(*)                                        AS work_units,
  SUM(w.turns)                                    AS turns,
  ROUND(SUM(w.notional_list_value_usd), 2)        AS notional_list_value_usd,
  ROUND(100.0 * SUM(w.notional_list_value_usd)
        / (SELECT SUM(notional_list_value_usd) FROM work_unit
            WHERE allowance_pool = w.allowance_pool), 1)
                                                  AS pct_of_pool,
  SUM(CASE WHEN v.justification = 'Overprovisioned' THEN 1 ELSE 0 END)
                                                  AS overprovisioned_units,
  ROUND(SUM(CASE WHEN v.justification = 'Overprovisioned'
                 THEN w.notional_list_value_usd ELSE 0 END), 2)
                                                  AS overprovisioned_notional_usd,
  'upper bound — assumes the cheaper tier finishes in the same tokens'
                                                  AS overprovisioned_caveat,
  'notional list value, not money billed'         AS value_label,
  'provisional'                                   AS classification_status
FROM work_unit w
LEFT JOIN classification c
  ON c.unit_id = w.id AND c.unit_grain = 'work_unit'
LEFT JOIN verdict v
  ON v.work_unit_id = w.id AND v.allowance_pool = w.allowance_pool
GROUP BY w.allowance_pool, c.ai_activity
ORDER BY SUM(w.notional_list_value_usd) DESC;
