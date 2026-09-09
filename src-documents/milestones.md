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

Tracked items carry their GitHub issue next to the status. The issue is a
worklist; **the answer belongs here** (see §6 *Issue tracking*).

---

## 1. Week one — before building anything

Two experiments. Neither produces code you keep. Both can invalidate weeks of
work, which is the point.

### W1 — The one-day spike *(status: **answered 2026-09-09, revised same day** · [#3](https://github.com/francisbrero/Model-Use-Index/issues/3) — see §5)*

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

**Result (2026-09-09).** Ran over 970 transcripts / 354 sessions. **37,781
unique Opus API responses, $23,059 notional list value.** Phoenix and its
worktrees are **73.4%** of that ($16,950), so the result speaks to the
operator's main workload.

> **Accounting note — the first two passes overstated cost by 91%.** See the
> streaming-duplication finding below. Every figure here is deduplicated.

**This answer was revised the same day. The first pass was wrong, and the way it
was wrong is itself the most useful thing W1 produced.**

**Attempt 1 — session shape (rejected).** Grouping by session and scoring
triviality from turn counts and tool histograms gave **0.03%**. Two independent
defects:

1. *Wrong signal.* An `Edit`-free session looked trivial, but under bypass-mode
   instructions agents edit via `sed`/heredocs through `Bash`. The naive cut read
   11.6% and was dominated by heavy mutating sessions — one was 1,567 turns ·
   798 `Bash` · $1,627. Counting `Bash` write verbs collapsed it to 0.03%.
2. *Wrong grain.* **The session is not the unit of work.** A 400-turn Phoenix
   session is a mix of hard debugging and mechanical release-shepherding.
   Scoring the whole session as one thing averages the interesting variance
   away, which is how attempt 1 reached "there is nothing here."

Neither defect touches *complexity*, which is the actual premise: the question
is not "was the session short" but **"did this work need a frontier model."**
Tool histograms cannot answer that.

**Attempt 2 — work units scored on the work itself.** Re-cut Phoenix into 1,823
work units (a user turn plus the Opus work it triggered) and scored each on six
signals read from the assistant's own output and tool use: ≥5 distinct files,
≥40 turns, debugging language, self-correction, subagent use, repeated test runs.

| Complexity score | Units | Notional | Share of Phoenix Opus |
|---|---|---|---|
| 0 — no signal at all | 1,146 | $7,361 | **43.4%** |
| 1 | 476 | $4,396 | 25.9% |
| 2 | 133 | $2,542 | 15.0% |
| 3+ | 68 | $2,651 | 15.6% |

Median cost is **$3.58** at score 0 against **$28.23** at score 3+. Score-0 work
at Sonnet list rates is $1,472 — an upper-bound saving of **$5,889**.

**Hand-read the twelve most expensive score-0 units** (the heuristic's worst
case, where a false negative would show). They are consistently
**release orchestration and CI shepherding**: confirm a SHA, verify images
pushed to ECR, check three required checks went green, bump an image tag,
transition a Jira ticket, wait on a nightly dispatch. Careful, stateful,
consequential — and almost entirely `Bash` plus judgment about what to check
next, not hard reasoning. Prompt text is no guide here either: bare acks and `continue`s account for ~12% of Phoenix
value, so **complexity lives in the work, not the ask.**

**Go/no-go:** **go, with a reframed headline.** The over-provisioning story
exists, but it is not "trivial sessions" — it is
**high-ceremony, low-reasoning orchestration work running on Opus.** Roughly
43% of Phoenix Opus value carries no complexity signal, and the hand-read says
that bucket is real rather than an artefact. That is A1, but A1 aimed at a
target the PRD does not currently name.

**A4 remains a strong second, on separate evidence.** 92.7% of Opus spend is
cache traffic (57.9% read, 34.8% write) against 7.2% output, so context
efficiency is a large independent lever regardless of how tiering lands.

**The methodological finding, which outranks both.** Two defensible heuristics
over the same data gave 0.03% and 36%. **The taxonomy is the product; the
plumbing is not.** A classifier that scores session shape or prompt text will
confidently produce a wrong report. This raises the stakes on the gold set (R1)
sharply — it is now the load-bearing deliverable, not a tedious calendar day.

**W1 closed the loop by hand on the first offender.** Phoenix has a
`/release-prod` slash command that was never configured to delegate to a cheaper
subagent, unlike other routines in that repo. Attributing from the
`attributionSkill` anchor to end of session:

| | |
|---|---|
| Release runs observed | 10 |
| Unique Opus API responses | 1,156 |
| Opus notional | **$1,511** — 8.9% of Phoenix Opus value |
| Same tokens at Sonnet list | $302 |
| Upper-bound saving | **$1,209 (80% of the routine, 7.1% of Phoenix Opus)** |
| Per release run | $151 → $30 |

`/release-prod` is the identifiable head of a larger orchestration tail, and an
instance of the dashboard category *agentic ops run on Opus*.

**This is the whole product in one instance:** transcript analysis → identify a
named offender → change the harness (delegate the routine to Sonnet, escalate to
Opus when something is non-vanilla) → banked reduction.

**The dashboard remains the deliverable — its job is to surface *categories*, not
individual fixes.** `/release-prod` is one instance of a class ("agentic ops run
on Opus"); the dashboard's output is that class and its siblings — testing run on
Opus, agentic ops run on Opus — ranked by reclaimable headroom. The operator
reads the category, then goes and finds the specific commands inside it. So the
taxonomy's top level should be **the kind of work**, because that is the level at
which a harness change gets made.

**`attributionSkill` is the anchor, and it undercounts badly.** It tags a
*contiguous run* of turns — the skill invocation itself (turns 642–652, 384–442,
631–695 in three sessions) — then stops, while the work that follows carries most
of the cost. Naive grouping by the field gives `/release-prod` a small fraction of its
anchored **$1,511** — an order-of-magnitude undercount. So the field is reliable for
*identifying* which routine ran and useless for *costing* it. **Attributing spend
from an anchor to the end of its arc is a real normalisation problem, and it is
not in the TD.** That is a Phase 0 question the PRD does not currently ask.

**Incidental answers.** U4REF: `message.usage` was present on **80,037 / 80,037**
assistant messages — 0 missing, 0 unparseable lines across 970 files. Records
also carry `version`, `cwd`, `gitBranch`, `isSidechain` and `requestId`, so
invariant 7's drift-bisect plan is viable. U8 rehearsal: `sessionId` grouping
works, but **sidechain turns bill into the parent session** — up to 2,102 in one
session — so subagent attribution is a real unknown. A `subagents` pseudo-project
holds $3,844 across 573 sessions, separate from any repo directory.

The spike script was deleted, per the issue.

### W2 — Test the central hypothesis by hand *(status: open · [#4](https://github.com/francisbrero/Model-Use-Index/issues/4))*

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

#### U10 · How do you bound a routine's cost arc from its `attributionSkill` anchor? `answered 2026-09-09` · [#13](https://github.com/francisbrero/Model-Use-Index/issues/13)

Raised by W1, absent from the TD. **The only unknown that blocked the first E2E
slice** — it defines the grain of `work_unit` (PRD §6.1), and the verdict engine
scores a work unit, so wrong boundaries give wrong verdicts silently.

**Answer: attribute from the anchor to the next anchor of any skill, else to
session end.** Rule id `u10-next-anchor-v1`.

Measured over 991 transcripts / 185 sessions / 383 anchor runs, deduplicated by
`(message.id, requestId)` with max per usage field (invariant 10). All dollar
figures are **notional list value**; Opus total $23,473, which reproduces W1's
$23,059 within 2%.

**Shape distribution.** Anchor tag length: median 15 turns, p90 36, max 272.
Turns from tag end to session end: median 69, p90 405, max 2,480 — so the tag
covers a small and highly variable fraction of the arc, confirming invariant 11.
Of 137 anchored sessions, **110 carry more than one anchor run** and 40 carry
more than one distinct skill; median 2 runs per anchored session, max 9.

**That last number is why W1's own baseline had to be replaced.** W1 used
*anchor → session end*. With two or more anchors per session the arcs overlap,
and re-scored properly that rule double-counts **$13,118 of Opus value** and
gives `/release-prod` only $314. It reproduced $1,511 in W1 only because W1 read
the release sessions by hand, where the overlap does not bite.

**Candidates scored against W1's $1,511 hand-read regression target:**

Read *Attributed* and *Overlap* together: the two rules that reach 92.6% cover
the same turns, but only one of them covers each turn once.

| Rule | `/release-prod` | vs target | Attributed | Double-counted |
|---|---|---|---|---|
| tagged turns only (naive) | $170 | 0.11× | 9.0% | $0 |
| anchor → session end (W1 baseline) | $314 | 0.21× | 92.6% | **$13,118** |
| **anchor → next anchor, else session end** | **$1,447** | **0.96×** | **92.6%** | **$0** |
| next anchor + `cwd`/`gitBranch` change | $1,036 | 0.69× | 21.4% | $0 |
| next anchor + 30-min idle gap | $432 | 0.29× | 31.3% | $0 |
| next anchor + 60-min idle gap | $803 | 0.53× | 42.1% | $0 |

**Why the two intuitive refinements both lose.** They cut the arc exactly where
the routine is doing its job:

- **Idle-time thresholds.** Real release arcs contain legitimate long waits — on
  CI, on ArgoCD sync, on review. Observed *within* single `/release-prod` arcs:
  gaps of 529, 699, 1,730 and **8,605 minutes** (six days). A gap is not evidence
  the arc ended; it is evidence the routine is waiting.
- **`cwd`/`gitBranch` change.** Release and deploy work legitimately moves across
  worktrees and branches — up to 47 turns of one arc sit on a different context
  than its anchor. Context change is a normal event inside an arc.

**Known error mode, stated as required.** The rule is *generous at the tail*: the
last anchor in a session absorbs everything to session end, including genuinely
unrelated work that follows. Sensitivity says this is not load-bearing — capping
the final arc at +150 turns moves `/release-prod` by 1.2% ($1,429) and the
attributed total by 5%. Capping at +50 turns costs 21%, so **do not cap tightly.**
Merging same-skill re-invocations into one arc changes nothing (no `/release-prod`
run is adjacent to another), so re-invocation is treated as a boundary.

**Regression target for `normalize/work_unit.py`:** assert on **$1,447 ± 5%**
(`[$1,375, $1,519]`) — the rule's *own* output over 10 runs, $145/run.
W1's **$1,511** is the independent hand-read validation reference, not the test's
centre. Two distinct numbers, deliberately:

- The test must assert a figure the rule can recompute from `raw_event` alone
  (invariant 2b). $1,447 is that figure; $1,511 came partly from human reading.
- **Centring the test on $1,511 ± 5% would be self-contradictory.** That interval
  is `[$1,435, $1,587]`, which *excludes* the $1,429 produced by the +150-turn
  cap this same entry calls acceptable. Centring on $1,447 contains both $1,429
  and $1,511, so the tolerance and the sensitivity analysis agree.

Per-run spread is wide and genuinely so: min $28, median $138, max $271,
stdev $85 — so a per-run assertion would be far looser than the 10-run total.

**Unattributable remainder — 7.4% of Opus notional list value ($1,731).** 6.0%
($1,416, 48 sessions) is sessions with no anchor at all; 1.3% ($315) is work
before a session's first anchor. This must be a labelled row in the dashboard,
not silently dropped. Sidechain turns hold $1,966 (8.4%), of which $1,737 falls
inside an anchor arc — so per-routine figures include their subagent cost, which
is correct, but must not also be counted alongside it (U8, invariant 10 §6).

**Cross-session arcs are not resolved.** 66 sessions end with the anchor tag
still on the final turn, so a routine continuing into a later session is
plausible; nothing joins them today. Left open deliberately — it is a Tier 2
concern for `work_unit`, and the 7.4% remainder bounds its size.

**Implementation notes.** `attributionSkill` appears on **`assistant` records
only** (17,180; never on `user`/`system`/`attachment`/`mode`), so a normaliser
reading assistant records for `usage` sees every anchor for free. The tag repeats
per content block, so anchor runs must be derived *after* invariant-10 dedup —
the 383 runs above collapse from those 17,180 records. Turn order must be
`(timestamp, file position)`: "the next anchor" is only meaningful in time.

Fixture `tests/fixtures/anchor_shapes/` + reference implementation
`tests/test_anchor_arc.py` (43 tests). It implements the **rejected** candidates
alongside the chosen rule, so the double-count comparison above is executable
rather than merely asserted. It sits in `tests/` because nothing is built yet
(MS §1); `normalize/work_unit.py` should import it and drop the local copy.

#### U1 · Do Codex session logs carry token counts? `open` · [#6](https://github.com/francisbrero/Model-Use-Index/issues/6)
- **Cost to resolve:** ~1 hour. Run a Codex subagent; locate and inspect its records.
- **Blocks:** PRD §5.1 Source E · G6 · TD §12 build order step 7
- **If the answer is bad:** G6 collapses. An OpenAI-side gateway moves from Phase 4a to Phase 1 — a schedule change, not a design tweak.
- **Answer:**

#### U2 · How do subagent runs appear on disk? `open` · [#7](https://github.com/francisbrero/Model-Use-Index/issues/7)
- **Cost:** ~30 min. Spawn a known subagent; diff `~/.claude/projects/` before and after.
- **Blocks:** PRD §5.4 · G3 · Phase 3 sentiment work
- **If the answer is bad:** Silently misattributes a large share of consumption to the main thread. **This one doesn't fail loudly** — the numbers just quietly mean something other than what they say, and you find out months later.
- **Note:** Research returned contradictory accounts (inlined with `isSidechain` vs. separate files). Likely version-dependent. Hooks are the belt-and-braces answer either way.
- **Answer:**

#### U3 · Is allowance consumption machine-readable? `open` · [#8](https://github.com/francisbrero/Model-Use-Index/issues/8)
- **Cost:** ~1 hour. Inspect OTel output, `/usage` internals, and the error payload on a limit hit.
- **Blocks:** PRD §6.2 · the headline number on every screen
- **If the answer is bad:** Capacity must be *fitted* from limit-hit events, which runs on a calendar clock you cannot compress. Dashboard falls back to share-of-period until the fit converges.
- **Answer:**

#### U3a · Do past rate-limit hits already appear in existing transcripts? `open` · [#5](https://github.com/francisbrero/Model-Use-Index/issues/5)
- **Cost:** ~20 min. Grep backfilled `raw_event` for rate-limit `api_error` records.
- **Why it's called out separately:** **This is the highest-leverage check on the list.** If historical limit hits are already on disk, backfill hands you calibration data on day one instead of in six weeks. Nothing else on this register compresses the schedule as much.
- **Answer:**

#### U4 · Does `message.usage` appear on every assistant message? `open` · [#9](https://github.com/francisbrero/Model-Use-Index/issues/9)
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

### M0 · Phase 0 memo — *target: end of week 1* · [#10](https://github.com/francisbrero/Model-Use-Index/issues/10)
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

### R1 · The gold-set day gets skipped `active` · **escalated 2026-09-09 (W1)**
A full day of tedious hand-labelling with no visible output. It will feel
skippable every single time you look at it. It is the difference between a report
you act on and a report you quietly second-guess.
**W1 escalated this from a discipline risk to the project's central risk.** Two
defensible heuristics over the same Phoenix data disagreed by three orders of
magnitude — 0.03% by session shape, 43.4% by work-unit complexity. Both looked
reasonable while being written. The classifier is therefore not a component that
supports the report; **it is the report**, and there is no way to tell a good one
from a bad one without hand-labelled ground truth.
**Mitigation:** schedule it as a named day in the calendar, not as a task inside
Phase 2 where it can be absorbed. Seed it from W1's hand-read of the twelve most
expensive score-0 Phoenix units — orchestration/CI-shepherding work is the label
boundary that matters most and the one most easily got wrong.

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
| 2026-09-09 | W1 | *(superseded same day — see the two rows below)* Session-shape triviality reads **0.03%**. | Withdrawn. The session was the wrong grain and tool histograms the wrong signal. |
| 2026-09-09 | W1 | *(figures superseded — see the accounting rows below; the finding stands)* **36.1% of Phoenix Opus value ($11,486 of $31,825) is work units with no complexity signal.** Hand-read of the 12 most expensive: release orchestration and CI shepherding. | **Go — with a reframed headline.** A1 survives, but aimed at *high-ceremony low-reasoning orchestration*, not "trivial sessions". PRD must name this target. |
| 2026-09-09 | W1 | **Two defensible heuristics over the same data gave 0.03% and 36%.** Session shape and prompt text both mislead; `approved` triggered $247 of work. | **The taxonomy is the product.** R1 (gold set) is promoted to load-bearing — a wrong classifier yields a confidently wrong report. |
| 2026-09-09 | W1 | Phoenix + worktrees are **72.8%** of all Opus notional value. | The result speaks to the main workload; no re-run against a different corpus needed. |
| 2026-09-09 | W1 | *(figures superseded — see below)* **First offender: Phoenix `/release-prod`.** 10 runs, $2,814 Opus, $563 at Sonnet — **$2,251 upper-bound saving, 7.1% of Phoenix Opus, from one unconfigured routine.** $281/run → $56/run. | **Proves the E2E loop end to end**: analysis → named offender → harness change → banked reduction. The deliverable is a ranked list of harness changes, not a dashboard. |
| 2026-09-09 | W1 | `attributionSkill` tags only a contiguous run of turns, not the arc the routine drives. | The field identifies routines but cannot cost them. **Anchor-to-arc attribution is a new Phase 0 question**, absent from the TD. |
| 2026-09-09 | **W1 accounting** | **Summing `usage` per JSONL record overstates cost by 91%** ($43,972 → $23,059). Claude Code writes **one assistant record per content block**, each repeating the *same* `usage` object; 34,314 of 72,083 Opus records were duplicates. | **New invariant.** Dedup by `(message.id, requestId)` before any arithmetic. This is the single easiest way for the tool to be confidently wrong. |
| 2026-09-09 | **W1 accounting** | Within a duplicate group, **5,951 groups carry differing `output_tokens`** — a partial streaming snapshot first, the final count later. First-seen dedup *undercounts* output. | Take **max per field** across the group, not first and not last-by-file-order. |
| 2026-09-09 | **W1 accounting** | Publicly known: ccusage #888, claude-code #5034, claude-devtools #74 all describe this; one report measures 51–55% of entries as duplicates. | Not a local quirk. Cite these in the TD so the dedup rule is never "simplified" away. |
| 2026-09-09 | W1 | **Corrected:** all Opus **$23,059**; Phoenix **$16,950 (73.4%)**; score-0 work **$7,361 = 43.4%** of Phoenix Opus (was 36.1%); `/release-prod` **$1,511 → $302 at Sonnet, $1,209 saving**, $151→$30 per run. | **Every ratio survived; only the levels halved.** Duplication was not biased toward complex work, so the go-with-reframed-headline verdict is unchanged and slightly stronger. |
| 2026-09-09 | W1 | The dashboard's role: surface **categories** (testing on Opus, agentic ops on Opus), not individual fixes. `/release-prod` is one instance of *agentic ops on Opus*. | **Taxonomy's top level should be kind-of-work**, since that is the level a harness change is made at. |
| 2026-09-09 | W1 | *(pre-dedup figures; corrected below)* **93.2% of Opus notional value is cache traffic** (54.7% read, 38.5% write); output is 6.8%. **Deduplicated: 92.7% cache traffic** (57.9% read, 34.8% write), output 7.2%. | **A4 is a strong second headline** on independent evidence — the ratio barely moved under correction. |
| 2026-09-09 | W1 | The naive `no Edit` cut reads 11.6% but is a false positive — `Bash`-driven edits. | Any triviality rule must classify `Bash` command verbs, not just tool names. Feeds the taxonomy. |
| 2026-09-09 | U4REF | `message.usage` present on **80,037/80,037** assistant messages; 0 bad lines in 970 files. | Source A token capture is sound. `version`/`cwd`/`gitBranch`/`isSidechain` also present — invariant 7 drift-bisect is viable. |
| 2026-09-09 | U8 (rehearsal) | `sessionId` grouping works, but sidechain turns bill into the parent session (one session: 2,102 sidechain turns). | Subagent attribution is a genuine open unknown; don't assume per-agent split comes free. |
| 2026-09-09 | **U10** | **Bounding rule: anchor → next anchor of any skill, else session end** (`u10-next-anchor-v1`). Reproduces `/release-prod` at **$1,447 notional list value over 10 runs** — W1's hand-read $1,511 within −4.3%. | **`work_unit` has a grain.** The first E2E slice is unblocked; the rule goes into `normalize/work_unit.py` asserting **$1,447 ± 5%** — the rule's own reproducible output (invariant 2b), with $1,511 kept as the separate hand-read reference. Centring on $1,511 ± 5% would exclude the $1,429 the accepted tail-cap variant produces. |
| 2026-09-09 | **U10** | **W1's own baseline was wrong at scale.** *Anchor → session end* double-counts **$13,118 of Opus notional value**, because **110 of 137 anchored sessions carry more than one anchor** (median 2, max 9). Re-scored, it gives `/release-prod` $314, not $1,511. | W1's figure was right only because the release sessions were read by hand. **Overlap is the metric that separates these rules**, and it must be asserted as zero in the normaliser's tests. |
| 2026-09-09 | **U10** | **Idle-gap and `cwd`/`gitBranch` thresholds both fail.** Single `/release-prod` arcs legitimately contain gaps of 529, 699, 1,730 and **8,605 minutes** (waiting on CI, ArgoCD, review) and move across up to 47 turns of other branches. Idle-30 recovers 29% of target; context-change 69%. | **Do not add either as a boundary.** They cut the arc exactly where the routine is waiting or switching worktrees — both normal events *inside* an arc. Recorded so it isn't re-proposed. |
| 2026-09-09 | **U10** | Known error mode: the rule is **generous at the tail** — the last anchor absorbs to session end. Capping that arc at +150 turns moves `/release-prod` 1.2%; at +50 turns, 21%. | Accepted as-is; **don't cap tightly.** The generosity is bounded and the alternative loses more than it fixes. |
| 2026-09-09 | **U10** | **Unattributable remainder: 7.4% of Opus notional list value ($1,731)** — 6.0% sessions with no anchor, 1.3% pre-first-anchor work. Sidechain turns are $1,966 (8.4%), $1,737 of it inside an arc. | Must be a **labelled dashboard row**, not dropped. Per-routine figures include subagent cost by construction — never also count it alongside (U8). |
| 2026-09-09 | **U10** | **Cross-session arcs unresolved.** 66 sessions end with the anchor tag still on the final turn. | Left open deliberately — Tier 2 for `work_unit`; the 7.4% remainder bounds how much it can matter. |

---

## 6. Next three actions

1. ~~**W1**~~ ([#3](https://github.com/francisbrero/Model-Use-Index/issues/3))
   — the one-day spike. **Done 2026-09-09: go, reframed. 43.4% of Phoenix Opus
   value shows no complexity signal — release orchestration and CI shepherding
   on Opus. A4 is a strong second at 93% cache traffic.** See §1.
2. **W2** ([#4](https://github.com/francisbrero/Model-Use-Index/issues/4)) —
   hand-test the `Agentic / Medium` hypothesis on Haiku. W1 lowered the stakes
   here — the 25% misallocation figure it defends is now a secondary analysis,
   not the headline — but it is still the cheapest way to find out whether the
   tier matrix is trustworthy at all, so it still runs before Phase 0.
3. **U3a** ([#5](https://github.com/francisbrero/Model-Use-Index/issues/5)) —
   grep existing history for past rate-limit errors. Twenty minutes, and it may
   save six weeks of waiting for calibration data. **W1 promoted this**: with A1
   re-aimed, A2 (under-provisioning) is a leading candidate for the second
   headline, and U3a is its gating evidence.

**`U10` is resolved out of band** ([#13](https://github.com/francisbrero/Model-Use-Index/issues/13),
answered 2026-09-09) — it was the only unknown blocking the first E2E slice, and
the slice's step-4 acceptance test now has a rule and a numeric target
(`/release-prod` = $1,447 ± 5% notional list value, against W1's $1,511 hand-read). That unblocks the slice; it
does not promote it ahead of W2 and U3a, which still gate committing to the
build.

Everything else waits on these three. **A PRD emphasis pass is now queued behind
W2** — A1 must be re-aimed at high-ceremony low-reasoning orchestration (not
"trivial sessions"), and A4 named as the second headline. Do not fix Phase 0
scope until it lands.

**W1 produced a fourth action, and it may outrank the first three.** Configure
Phoenix `/release-prod` to delegate to Sonnet with an Opus escalation path for
non-vanilla runs. It is a harness edit in another repo, needs none of this tool,
and banks an estimated $1,209 upper bound immediately. It is also the honest test
of R2: record the realised saving on the next release run and compare it to that
estimate, before the tool exists to make the same claim at scale.

**W1 also promoted R1.** The gold set is no longer a tedious day that risks being
skipped — it is the deliverable the whole report's credibility rests on, because
W1 demonstrated two defensible heuristics disagreeing by three orders of
magnitude on the same data.

### Issue tracking

The week-one gates and the Tier 1 unknowns are tracked as GitHub issues; **this
document stays the source of truth for the answers.** Record each answer here
(inline, then §5) and close the issue against it — don't let the issue thread
become the register.

| Register ID | Issue | Tier | Status |
|---|---|---|---|
| `W1` | [#3](https://github.com/francisbrero/Model-Use-Index/issues/3) | Week one — gate | **answered 2026-09-09** |
| `W2` | [#4](https://github.com/francisbrero/Model-Use-Index/issues/4) | Week one — gate | open |
| `U3a` | [#5](https://github.com/francisbrero/Model-Use-Index/issues/5) | Tier 1 | open |
| `U10` | [#13](https://github.com/francisbrero/Model-Use-Index/issues/13) | Tier 1 — **slice blocker** | **answered 2026-09-09** |
| `U1` | [#6](https://github.com/francisbrero/Model-Use-Index/issues/6) | Tier 1 | open |
| `U2` | [#7](https://github.com/francisbrero/Model-Use-Index/issues/7) | Tier 1 | open |
| `U3` | [#8](https://github.com/francisbrero/Model-Use-Index/issues/8) | Tier 1 | open |
| `U4` | [#9](https://github.com/francisbrero/Model-Use-Index/issues/9) | Tier 1 | **answered incidentally by W1** (U4REF) |
| `M0` | [#10](https://github.com/francisbrero/Model-Use-Index/issues/10) | Milestone | open |

Tier 2 (`U5`–`U7`) is tracked on the M0 checklist rather than as separate issues;
Tier 3 (`U8`, `U9`) gets an issue when its phase opens. **W1 rehearsed `U8`** —
sidechain turns bill to the parent session — so that issue should carry the
rehearsal note when it opens.
