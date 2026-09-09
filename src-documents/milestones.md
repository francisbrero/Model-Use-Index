# Model Use Index — Milestones & Unknowns

**A working register. Update it in place; don't rewrite it.**

| | |
|---|---|
| **Owner** | Francis Brero |
| **Status** | Open — nothing resolved yet |
| **Date opened** | 9 September 2026 |
| **Companions** | *Model Use Index* (PRD — what and why) · *Three Processes and a Database* (TD — how) |

---

## How to use this

Three registers and a log:

- **§1 Week one** — what to do before committing to the build at all.
- **§2 Unknowns** (`U1`–`U9`) — each has a status, a cost to resolve, and an
  explicit *what changes if the answer is bad*. Fill in the answer inline when
  you get it; move it to §5.
- **§3 Milestones** (`M0`–`M5`) — each has a definition of done that is a
  *measurement*, not a feeling.
- **§4 Standing risks** — the ones that don't resolve, only get managed.
- **§5 Answer log** — append-only. Date, question, answer, what it changed.

Statuses: `open` · `in progress` · `answered` · `moot`

---

## 1. Week one — before building anything

Two experiments. Neither produces code you keep. Both can invalidate weeks of
work, which is the point.

### W1 — The one-day spike *(status: **answered 2026-09-09** — see §5)*

A throwaway script over your **existing** transcript history. Not a prototype —
delete it afterwards.

```
glob   ~/.claude/projects/**/*.jsonl
pull   model + message.usage from every assistant message
group  by session; build a tool histogram per session
answer how much Opus consumption went to sessions that look trivial
       (few turns · no Edit · mostly Read/Grep/Glob)
```

**Why this first.** That single number is the whole thesis in miniature.

| Result | What it means |
|---|---|
| ~20%+ | Real project. Build it properly. |
| ~3% | The over-provisioning story isn't there. The interesting question is probably **context efficiency (A4)** or **under-provisioning (A2)** instead — reshape the PRD's emphasis before building. |

Either answer is worth a day. This is also a free rehearsal for U4 and U8.

**Result (2026-09-09).** Ran over 970 transcripts / 354 sessions; 180 sessions
carry Opus consumption, 16.87 B Opus tokens, **$43,683 notional list value**.

| Definition of "trivial" | Sessions | Share of Opus notional value |
|---|---|---|
| No mutation of any kind (incl. `Bash` writes) | 8 | **0.03%** |
| ≤ 25 assistant turns, any work | 27 | 0.2% |
| ≤ 50 assistant turns, any work | 40 | 0.6% |
| ≤ 5 mutations total | 28 | 0.2% |
| `Edit`-tool-free only (naive — **wrong**, see below) | 51 | 11.6% |

**The naive `no Edit` cut is a false positive and must not be quoted.** Under
this repo's own bypass-mode instruction, agents edit files with `sed`/heredocs
through `Bash`, so an `Edit`-free session is often a heavy mutating session. The
11.6% bucket is dominated by sessions like *1,567 turns · 798 `Bash` · 412
sidechain · $1,627* — the opposite of trivial. Counting `Bash` write verbs as
mutations collapses that 11.6% to **0.03%**.

**This is the ~3% branch, and then some.** 93.6% of Opus notional value sits in
sessions over 250 assistant turns. There is no meaningful population of trivial
Opus sessions to reclaim; the over-provisioning story does not exist at this
operator's usage profile.

**Where the value actually is — context, not model tier:**

| Component | Opus tokens | Notional | Share |
|---|---|---|---|
| cache read | 15.93 B | $23,895 | **54.7%** |
| cache write | 897 M | $16,820 | 38.5% |
| output | 39.5 M | $2,964 | 6.8% |
| input | 297 K | $4 | 0.0% |

**93.2% of Opus spend is cache traffic, not generation.** That is A4 (context
efficiency), not A1 (over-provisioning).

**Go/no-go:** **No-go on "over-provisioning as the headline."** A1 stays as a
secondary analysis; **A4 becomes the headline**, with A2 (under-provisioning) the
second candidate pending U3a. The PRD's emphasis needs reshaping before Phase 0
scope is fixed.

**Incidental answers.** U4REF: `message.usage` was present on **80,037 / 80,037**
assistant messages — 0 missing, 0 unparseable lines across 970 files. The field
carries `cache_creation_input_tokens`, `cache_read_input_tokens`,
`service_tier`, and a nested `cache_creation` 1h/5m split. Records also carry
`version`, `cwd`, `gitBranch`, `isSidechain` and `requestId`, so invariant 7's
drift-bisect-by-version plan is viable. U8 rehearsal: session grouping by
`sessionId` worked, but **`isSidechain` turns are billed into the parent session**
— up to 2,102 sidechain turns in one session — so subagent attribution is a real
unknown, not a formality.

The spike script was deleted, per the issue.

### W2 — Test the central hypothesis by hand *(status: open)*

**The tier matrix came from a screenshot of somebody else's report.** It
reproduces that report 28/28 — which proves fidelity to the source, not that the
source was right. The headline finding rests entirely on one cell:
`Agentic / Medium` expects `small`. If that cell is really `mid`, the 25%
misallocation figure evaporates.

Pick 20 recent Agentic/Medium tasks you ran on Sonnet. Re-run five or six on
Haiku by hand. Do they land?

Half a day, and it validates or kills the central hypothesis before a line of the
tool is written. **The finding you are most excited about is the one with the
least evidence behind it.** Correct that now rather than in Phase 3.

---

## 2. Unknown register

### Tier 1 — resolve in the first two days

These change the plan, not just the implementation.

#### U1 · Do Codex session logs carry token counts? `open`
- **Cost to resolve:** ~1 hour. Run a Codex subagent; locate and inspect its records.
- **Blocks:** PRD §5.1 Source E · G6 · TD §12 build order step 7
- **If the answer is bad:** G6 collapses. An OpenAI-side gateway moves from Phase 4a to Phase 1 — a schedule change, not a design tweak.
- **Answer:**

#### U2 · How do subagent runs appear on disk? `open`
- **Cost:** ~30 min. Spawn a known subagent; diff `~/.claude/projects/` before and after.
- **Blocks:** PRD §5.4 · G3 · Phase 3 sentiment work
- **If the answer is bad:** Silently misattributes a large share of consumption to the main thread. **This one doesn't fail loudly** — the numbers just quietly mean something other than what they say, and you find out months later.
- **Note:** Research returned contradictory accounts (inlined with `isSidechain` vs. separate files). Likely version-dependent. Hooks are the belt-and-braces answer either way.
- **Answer:**

#### U3 · Is allowance consumption machine-readable? `open`
- **Cost:** ~1 hour. Inspect OTel output, `/usage` internals, and the error payload on a limit hit.
- **Blocks:** PRD §6.2 · the headline number on every screen
- **If the answer is bad:** Capacity must be *fitted* from limit-hit events, which runs on a calendar clock you cannot compress. Dashboard falls back to share-of-period until the fit converges.
- **Answer:**

#### U3a · Do past rate-limit hits already appear in existing transcripts? `open`
- **Cost:** ~20 min. Grep backfilled `raw_event` for rate-limit `api_error` records.
- **Why it's called out separately:** **This is the highest-leverage check on the list.** If historical limit hits are already on disk, backfill hands you calibration data on day one instead of in six weeks. Nothing else on this register compresses the schedule as much.
- **Answer:**

#### U4 · Does `message.usage` appear on every assistant message? `open`
- **Cost:** ~20 min (W1 answers this incidentally).
- **Blocks:** Every number in the system.
- **If the answer is bad:** Coverage target of 95% is unreachable from the transcript alone; OTel becomes load-bearing rather than a cross-check.
- **Answer:**

### Tier 2 — resolve during Phase 0, but they don't change the architecture

#### U5 · Which hooks fire on this version, with what payload? `open`
- **Cost:** ~1 hour. Register logging stubs for every candidate.
- **Blocks:** PRD §5.1 Source C. Especially `PreModelSwitch`, which is the free labelled data for A2.
- **If `PreModelSwitch` doesn't exist:** Under-provisioning loses its ground truth and falls back entirely to cohort thresholds. Worse, not fatal.
- **Answer:**

#### U6 · Does `OTEL_LOG_RAW_API_BODIES=1` work? `open`
- **Cost:** ~30 min.
- **Blocks:** A4 (context efficiency) only.
- **If the answer is bad:** A4 is not possible without a gateway, and we've decided against one. Drop A4 or accept a partial version from cache-token ratios alone.
- **Answer:**

#### U7 · Do transcript token counts agree with OTel metrics? `open`
- **Cost:** ~1 hour on a known workload.
- **Blocks:** PRD §5.3 reconciliation. Determines the authoritative source.
- **Answer:**

### Tier 3 — can't be resolved yet; scheduled, not investigated

#### U8 · Is the classifier good enough? `open until Phase 2`
- **Resolved by:** the gold set (§4 R1). Target ≥80% agreement on `work_type` and `task_complexity`.
- **Cannot be shortcut.** No amount of prompt work substitutes for 200 hand-labelled rows.

#### U9 · Is the tier matrix right? `open until Phase 3`
- **Partially testable now** — see W2.
- **Fully resolved by:** outcome data. Do `Acceptable (downgrade candidate)` rows actually show clean outcomes? If a tier assignment consistently produces under-provisioning signals, the matrix is wrong, not the run.

---

## 3. Milestone register

Framed as de-risking moments rather than as phases. Each definition of done is a
measurement.

### M0 · Phase 0 memo — *target: end of week 1*
**Done when:** U1–U7 each have a recorded answer in §5, with sample records
attached, and a go/no-go on the allowance model vs. direct read.
**Also produced:** the golden-file fixtures TD §11 needs. Collect them now; they
cost nothing extra while you're already looking at the records.

### M1 · First honest number — *target: end of week 2*
Backfilled history, normalised, reconciled.
**Done when:** Anthropic token totals reconcile with `/usage` within 2% over a
7-day window, reported by `mui doctor`.
**Why it matters:** this is when the project stops being speculative. Everything
before it is scaffolding.

### M2 · Datasette on real data — *days after M1*
**Done when:** you can browse and query captured data in a browser.
**Why it matters:** near-zero effort, and it's where capture bugs surface while
they're still cheap. Do not defer this to "when the real dashboard exists."

### M3 · First classified report — *target: week 3–4*
**Done when:** the Model Use Index renders, gold-set agreement ≥80%, `other`
label rate <10%, and it produces at least one over-provisioning finding you
agree with on inspection.

### M4 · First action taken — *no useful date; protect the gap*
**Done when:** a default model is actually changed because of what the tool said.
**Why it matters:** **this is where tools like this die.** Not with a failure —
they just get opened less each week until nobody opens them. Everything up to M3
is output. M4 is the first behaviour change.

### M5 · First verified action — *one week after M4*
**Done when:** the predicted headroom either materialised or didn't, and the gap
is written down.
**Why it matters:** the only milestone that is an *outcome*. If you protect one
thing in the schedule, protect M3 → M4 → M5.

---

## 4. Standing risks

Not unknowns — these don't get resolved, only managed.

### R1 · The gold-set day gets skipped `active`
A full day of tedious hand-labelling with no visible output. It will feel
skippable every single time you look at it. It is the difference between a report
you act on and a report you quietly second-guess.
**Mitigation:** schedule it as a named day in the calendar, not as a task inside
Phase 2 where it can be absorbed.

### R2 · Estimates over-promise and credibility rots `active`
Headroom reclaimable is an upper bound by construction — it assumes the cheaper
model finishes in the same tokens. It won't.
**Mitigation:** label it as an upper bound in the UI, and at M5 **publish the gap
between predicted and realised.** A tool that shows its own prediction error
stays trusted. One that quietly stops mentioning predictions does not.

### R3 · Silent ingestion failure `active`
A tool that stopped collecting three weeks ago but still renders a confident
dashboard is worse than no tool.
**Mitigation:** `mui doctor` is a first-class deliverable (TD §13), and the
data-quality view ships with the first dashboard, not after it.

### R4 · Scope creep into a product `active`
**Mitigation:** the non-goals in PRD §3 are load-bearing. Internal tooling, one
machine, one operator. Multi-user is a separate decision (4c), not a rollout.

### R5 · Schema drift breaks ingestion `managed by design`
Mitigated structurally rather than procedurally: the collector performs no
interpretation (TD §2.1), so a drift breaks parsing — which is re-runnable over
`raw_event` — rather than capture.

---

## 5. Answer log

Append-only. Date · question · answer · what it changed.

| Date | ID | Answer | Consequence |
|---|---|---|---|
| 2026-09-09 | W1 | Trivial-Opus share is **0.03%** of $43,683 notional (8 of 180 sessions). 93.6% of value is in 250+ turn sessions. | **No-go on over-provisioning as the headline.** A1 demoted to secondary. |
| 2026-09-09 | W1 | **93.2% of Opus notional value is cache traffic** (54.7% read, 38.5% write); output is 6.8%. | **A4 (context efficiency) becomes the headline analysis.** Reshape PRD emphasis before fixing Phase 0 scope. |
| 2026-09-09 | W1 | The naive `no Edit` cut reads 11.6% but is a false positive — `Bash`-driven edits. | Any future triviality rule must classify `Bash` command verbs, not just tool names. Feeds the taxonomy. |
| 2026-09-09 | U4REF | `message.usage` present on **80,037/80,037** assistant messages; 0 bad lines in 970 files. | Source A token capture is sound. `version`/`cwd`/`gitBranch`/`isSidechain` also present — invariant 7 drift-bisect is viable. |
| 2026-09-09 | U8 (rehearsal) | `sessionId` grouping works, but sidechain turns bill into the parent session (one session: 2,102 sidechain turns). | Subagent attribution is a genuine open unknown; don't assume per-agent split comes free. |

---

## 6. Next three actions

1. ~~**W1** — the one-day spike.~~ **Done 2026-09-09: 0.03%. No-go on the
   over-provisioning headline; A4 (context efficiency) takes its place.** See §1.
2. **W2** — hand-test the `Agentic / Medium` hypothesis on Haiku. W1 lowered the
   stakes here — the 25% misallocation figure it defends is now a secondary
   analysis, not the headline — but it is still the cheapest way to find out
   whether the tier matrix is trustworthy at all, so it still runs before Phase 0.
3. **U3a** — grep existing history for past rate-limit errors. Twenty minutes,
   and it may save six weeks of waiting for calibration data. **W1 promoted
   this**: with A1 demoted, A2 (under-provisioning) is a leading candidate for
   the second headline, and U3a is its gating evidence.

Everything else waits on these three. **A PRD emphasis pass (A4 to the front)
is now queued behind W2** — do not fix Phase 0 scope until it lands.