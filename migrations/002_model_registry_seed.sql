-- 002_model_registry_seed.sql — the versioned rate registry.
--
-- Rates are DATA, not constants in an analysis (token-accounting §2). Storing
-- tokens and repricing against a versioned registry means a rate correction
-- re-values history instead of corrupting it (PRD §6.3).
--
-- Every figure these rates produce is NOTIONAL LIST VALUE. We are on seat
-- subscriptions, not metered billing (invariant 5) — no dollar figure derived
-- from this table is money anyone was billed. It exists to RANK work, and the
-- primary measure (allowance headroom) is deliberately not computed by this
-- slice at all.
--
-- All four fields are priced. Cache traffic is ~93% of Opus notional value
-- here (57.9% read, 34.8% write) against 7.2% output, so a registry that
-- priced only input and output would miss almost all of it.
--
-- Patterns are globs so a version-pinned id resolves to the same tier as its
-- unpinned form. Resolution is longest-pattern-first and fails loudly on no
-- match; a silent tier default would corrupt every `tier_delta` in `verdict`.

INSERT OR REPLACE INTO model_registry
  (version, provider, model_pattern, tier, allowance_pool,
   is_billable, usd_per_mtok_in, usd_per_mtok_out, usd_per_mtok_cache_write,
   usd_per_mtok_cache_read, effective_from)
VALUES
  -- Frontier
  ('2026-09-11', 'anthropic', 'claude-opus-5*',    'frontier', 'anthropic-seat',
   1, 15.00, 75.00, 18.75, 1.50, '2026-01-01'),
  ('2026-09-11', 'anthropic', 'claude-opus-4*',    'frontier', 'anthropic-seat',
   1, 15.00, 75.00, 18.75, 1.50, '2026-01-01'),
  -- Fable 5.1 is priced at Opus rates pending a published figure; flagged
  -- because every other row here is a familiar published rate.
  ('2026-09-11', 'anthropic', 'claude-fable-5*',   'frontier', 'anthropic-seat',
   1, 15.00, 75.00, 18.75, 1.50, '2026-01-01'),
  -- Mid
  ('2026-09-11', 'anthropic', 'claude-sonnet-5*',  'mid',      'anthropic-seat',
    1, 3.00, 15.00,  3.75, 0.30, '2026-01-01'),
  ('2026-09-11', 'anthropic', 'claude-sonnet-4*',  'mid',      'anthropic-seat',
    1, 3.00, 15.00,  3.75, 0.30, '2026-01-01'),
  -- Small
  ('2026-09-11', 'anthropic', 'claude-haiku-4-5*', 'small',    'anthropic-seat',
    1, 1.00,  5.00,  1.25, 0.10, '2026-01-01'),
  ('2026-09-11', 'anthropic', 'claude-haiku-4*',   'small',    'anthropic-seat',
    1, 1.00,  5.00,  1.25, 0.10, '2026-01-01'),
  ('2026-09-11', 'anthropic', 'claude-haiku-3*',   'small',    'anthropic-seat',
    1, 0.25,  1.25,  0.30, 0.03, '2026-01-01'),

  -- '<synthetic>' is not a model. Claude Code writes it as `message.model` on
  -- rate-limit and error records, whose usage is all zeros. A rate-limit hit
  -- is the only on-disk evidence of an allowance boundary (invariant 10b), and
  -- tier resolution fails loudly on unmatched models — so without a row here,
  -- capturing those records would force exactly the filter that invariant
  -- forbids.
  --
  -- Tier is 'small' and INERT: `is_billable = 0` keeps this row out of
  -- `used_tier` resolution entirely, so it never reaches PRD §8.2's ordinal
  -- arithmetic. Keeping the tier enum at three values is what makes that
  -- arithmetic total; a fourth value would coerce to 0 and read as
  -- `Justified`. Zero rates are correct rather than placeholder — these
  -- records carry no tokens, so they contribute no value by construction.
  ('2026-09-11', 'anthropic', '<synthetic>',       'small',    'anthropic-seat',
   0, 0.00,  0.00,  0.00, 0.00, '2026-01-01');
