# Phase 0 — Reconnaissance findings

Pure investigation. Its entire purpose is to replace six assumptions with facts
before anything is built on them (PRD §14 Phase 0).

**Exit criteria:** every question below answered with a sample record attached,
plus a go/no-go on the allowance model vs. direct read.

**Status:** not started.

> Do not commit real sample records here — `phase0/**` is gitignored except this
> file and the README. Paste **scrubbed, obviously synthetic** excerpts only, and
> keep the real ones in your local working copy.

---

## Q1 — How does a subagent run appear on disk?

**Why it blocks:** §5.4. Research returned contradictory accounts — inlined in
the parent transcript flagged `isSidechain: true`, versus a separate transcript
file with its own `sessionId`. Likely version-dependent. A wrong answer silently
misattributes a large fraction of subagent consumption to the main thread, and
both G3 and Phase 3 depend on getting it right.

**Method:** spawn a known subagent, diff `~/.claude/projects/`.

**Finding:**

**Sample record:**

**Consequence for the design:**

---

## Q2 — Where does Codex write session logs, and do they carry token counts?

**Why it blocks:** §5.1 Source E. The entire cross-provider story depends on it.
Without it, delegated work shows effort with no consumption, which makes those
rows look artificially *cheap* — inverting the verdict on exactly the rows we
most want to judge.

**Method:** run a Codex subagent; locate and inspect its records.

**Finding:**

**Sample record:**

**Fallback needed?** (An OpenAI-side gateway is Phase 4a, and only if the logs
prove insufficient.)

---

## Q3 — Is allowance consumption exposed programmatically, or must it be modelled?

**Why it blocks:** §6.2. Determines whether the primary measure (`allowance_pct`)
is *read* or *fitted* — a substantially different amount of work and a
substantially different confidence level.

**Method:** inspect OTel output, `/usage` internals, and API error payloads on a
limit hit.

**Finding:**

**Go/no-go on the allowance model:**

---

## Q4 — Does `OTEL_LOG_RAW_API_BODIES=1` work, and what does it emit?

**Why it blocks:** determines whether analysis A4 (assembled context window) is
possible at all. Currently **unverified** — reported in research, not confirmed.

**Method:** enable it, run a session, inspect collector output.

**Finding:**

**A4 possible?**

---

## Q5 — Do transcript token fields agree with OTel metrics?

**Why it blocks:** §5.3. Settles which source is authoritative. The rule is one
authoritative consumption source per provider; this is how we pick it, and a
persistent delta above 2% is a bug rather than rounding.

**Method:** run a known workload, reconcile the two.

**Finding:** (record the observed delta)

---

## Q6 — Which hooks fire on this version, with what payload?

**Why it blocks:** §5.1 Source C — and especially `PreModelSwitch`. A
Sonnet → Opus escalation is a human explicitly saying "this model is not working
for this task": ground truth for under-provisioning needing no classifier and no
thresholds, plus a free labelled dataset to calibrate everything else against.
If it doesn't fire, §10 A2 needs another bootstrap.

**Method:** register logging stubs for all candidate hooks.

Candidates: `SubagentStart` / `SubagentStop`, `PreModelSwitch` /
`PostModelSwitch`, `PreCompact`, `Stop` / `StopFailure`, `PreToolUse` (Bash).

| Hook | Fires? | Payload fields | Notes |
|---|---|---|---|
| `SubagentStart` | | | |
| `SubagentStop` | | | |
| `PreModelSwitch` | | | |
| `PostModelSwitch` | | | |
| `PreCompact` | | | |
| `Stop` | | | |
| `StopFailure` | | | |
| `PreToolUse` (Bash) | | | |

**Finding:**

---

## Memo — go/no-go

<!-- One page. What changed about the plan as a result of Phase 0? Which Phase 1
     assumptions survived, which didn't, and what does Phase 1 look like now? -->

---

## TRD open implementation questions (§15)

Distinct from Q1–Q6 above: those are about the product's unknowns, these about
the build. Phase 0 can cheaply settle the first two while it has the machine
instrumented; the rest are decided when real data volumes are known.

| # | Question | Lean | Settle by |
|---|---|---|---|
| I1 | OTLP receiver: full OpenTelemetry Collector, or ~100 lines of FastAPI? | Minimal receiver — keeps it in one process, no extra binary/config/supervisor. Revisit if protobuf handling gets fiddly. | Q4, while the collector is already running |
| I2 | File watching: `watchdog` or `fswatch`? | Either way a **periodic reconcile sweep is required** — FSEvents can coalesce and miss under rapid appends. Do not rely on events alone. | Q1/Q5, observed during backfill |
| I3 | What if the `codex` wrapper is bypassed (real binary, or absolute path)? | Detected as a Codex session log with no sidecar → already surfaces as `orphaned`. Decide: attempt timestamp-based joining, or just report. | Q2 |
| I4 | Must `mui-collect` survive Ollama being absent? | Yes. Confirm nothing in the collect path touches Ollama — that's the intent of the plane split. | Phase 1 step 2 (assert in tests) |
| I5 | Compression threshold and format for aged `raw_event` payloads | `zstd` is ~30% better than stdlib `zlib` but adds a dependency; probably not worth it. | Once real volumes are known |

**Note:** Phase 0's sample records are also the seed of the golden-file parser
fixtures (TRD §11) — the schema-drift regression suite. Scrub them, then keep
them under `tests/fixtures/` rather than discarding them with the scratch files.
