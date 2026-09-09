# Model Use Index — Milestones & Unknowns

**A working register. Update it in place; don't rewrite it.**

| | |
|---|---|
| **Owner** | Francis Brero |
| **Status** | Open — W1, U10 and U3a answered; **W2 is the last week-one gate**; slice scoped (#14) |
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

### W2 — Test the central hypothesis by hand *(status: **in progress** — redesigned Opus→Haiku 2026-09-09; worklist ready, six hand-runs outstanding · [#4](https://github.com/francisbrero/Model-Use-Index/issues/4) — see §5)*

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

**Redesigned 2026-09-09 — the Sonnet pool does not exist.** 97.9% of Sonnet
records are subagent turns; only 78 main-agent records survive, across two
one-shot Q&A sessions. The control is therefore **Opus, not Sonnet**, which
weakens the possible conclusion: Haiku failing means *Haiku cannot do this*, not
*Haiku is worse than Sonnet*. Candidate selection is done — 227 work units in
band, six selected, verdict rule fixed in advance in
[`phase0/w2-worklist.md`](../phase0/w2-worklist.md). **What remains is the six
hand-runs, which is the half-day and cannot be automated.**

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

Measured over 991 transcripts / 184 sessions / 383 anchor runs, deduplicated by
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
and re-scored properly that rule double-counts **$13,118 of Opus notional list
value** and
gives `/release-prod` only $314. It reproduced $1,511 in W1 only because W1 read
the release sessions by hand, where the overlap does not bite.

**Candidates scored against W1's $1,511 hand-read regression target:**

Read *Attributed* and *Double-counted* together: the two rules that reach 92.6% cover
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
(`[$1,375, $1,519]`) — the rule's *own* output over 10 runs, mean $145/run.
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

**Unattributable remainder — 7.4% of Opus notional list value ($1,730).** 6.0%
($1,415, 47 sessions) is sessions with no anchor at all; 1.3% ($315) is work
before a session's first anchor. (Exactly 7.337% = 6.002% + 1.336%, and
$1,415 + $315 = $1,730; the rounded components read as 7.3%.) This must be a labelled row in the dashboard,
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
the 383 runs above collapse from those 17,180 records.

Turn order must be `(timestamp, message.id)` — "the next anchor" is only
meaningful in time, and **the tie-break has to come from the record**, or arc
boundaries depend on how the rows were read rather than on what they say
(invariant 2b). Ordering ties by file position, or leaving them to SQL row
order, is not reproducible.

**The corpus grows while you measure it.** Re-running the loader gives a
slightly different Opus total each time — $23,473, then $23,574 notional list
value — because analysing transcripts inside Claude Code appends to the very
history being read. The whole difference is this project's own sessions ($121,
0.5%); excluding them reproduces $23,454. Two consequences to carry into `mui`:

- **Session counts and population percentages are as-of-a-moment**, so quote the
  corpus date beside them. The counts here are 184 sessions / 137 anchored / 47
  with no anchor — which is also where an earlier "185 / 48" in this entry came
  from: a miscount, since 137 + 47 = 184.
- **`/release-prod` stays at $1,447 over 10 runs across re-runs**, because the
  U10 work never invokes that routine. That is the argument for pinning the
  regression target to a *named routine* rather than a corpus-wide total: the
  drift moves the denominator and leaves the target untouched.


Measured, so the rule isn't defended by a story: **ties are almost absent — 1
group, 2 turns of 42,528 (0.005%), in 1 of those 184 sessions.** Both turns in it are
untagged sidechain turns, so today no tie can move an arc boundary. But
`message.id` order disagrees with file order in that one case, so the two rules
*do* diverge on real data, and the cost of getting determinism is one sort key.
Cheap insurance against an irreproducible number, not a live bug.

Fixture `tests/fixtures/anchor_shapes/` + reference implementation
`tests/test_anchor_arc.py` (100 tests over 11 synthetic sessions). It implements the **rejected** candidates
alongside the chosen rule, so the double-count comparison above is executable
rather than merely asserted. It sits in `tests/` because nothing is built yet
(MS §1); `normalize/work_unit.py` should import it and drop the local copy.

**What is and isn't reproducible from the repo.** The tests verify the *rule* —
boundary arithmetic, four-field pricing, conservation, dedup — at fixture scale.
The population figures above ($13,118, 92.6%, 7.4%, the candidate table) came
from a throwaway script over `~/.claude/projects/`, deleted like W1's. To redo
them: load every `type: "assistant"` record, dedup by `(message.id, requestId)`
taking max per usage field, group by session, order by `(timestamp,
message.id)`, derive contiguous `attributionSkill` runs, apply each candidate rule,
and sum Opus notional list value per skill while counting turns claimed more than
once. The 991-transcript corpus reproduces $23,473 total, which is the check that
the loader is right before trusting anything else it says.

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

#### U3a · Do past rate-limit hits already appear in existing transcripts? **`answered 2026-09-09`** · [#5](https://github.com/francisbrero/Model-Use-Index/issues/5)
- **Cost:** ~20 min. Grep backfilled `raw_event` for rate-limit `api_error` records.
- **Why it's called out separately:** **This is the highest-leverage check on the list.** If historical limit hits are already on disk, backfill hands you calibration data on day one instead of in six weeks. Nothing else on this register compresses the schedule as much.
- **Answer: yes — 29 records, but only 6 distinct limit episodes, and that is the number that matters.**

  **The record.** `error: "rate_limit"` on a synthetic assistant message —
  `message.model` is the literal string `<synthetic>`, `usage` is all zeros, and
  `apiErrorStatus` is `429`. It is a normal transcript line otherwise, carrying
  `timestamp`, `sessionId`, `requestId`, `version`, `cwd`, `gitBranch`,
  `isSidechain`. **It is not a `usage`-bearing record**, so invariant 10's dedup
  never sees it and no token arithmetic is affected. 29 records, 16 sessions, 9
  projects, `2026-07-30` → `2026-08-27`.

  **The 29 collapses to 6.** A single limit event fires one record per *live
  session*, all naming the same reset time — one episode on 2026-08-21 hit 8
  records across 7 sessions within four minutes. **Deduplicate by stated reset
  target, not by record**, or the fit is trained on the operator's parallelism
  rather than on the limit. Of the 6: **4 session (5-hour) limits, 1 weekly
  (7-day), 1 org monthly spend.**

  **Fields available.** Two shapes, split by client version:
  - `2.1.220` (28 of 29) — reset time only as **display text** in
    `message.content[].text`: *"You've hit your session limit · resets 11:40pm
    (America/Los_Angeles)"*. Local wall-clock, no date on the 5-hour form,
    tz-named. Parseable, but it is a UI string and invariant 7 applies to it
    with force.
  - `2.1.245` (1 of 29) — additionally carries a **structured `quotaLimits`
    object**: `{status, resetsAt (unix epoch), rateLimitType ("seven_day"),
    unifiedRateLimitFallbackAvailable, overageStatus, overageDisabledReason,
    isUsingOverage}`. **This is the field to key the allowance model on.**
    Prefer it; fall back to text parsing for older records.
- **Go/no-go on "calibrate from backfill": qualified go — backfill for the
  *shape*, live capture for the *fit*.** Backfill is worth doing now and hands
  over free evidence: it fixes the record shape, proves the 5-hour and 7-day
  windows are both observable, and gives 6 real boundary points with 75–2,097
  deduped assistant records in the 5 hours preceding each. That is enough to
  build and sanity-check `enrich/allowance.py` today rather than in six weeks.
  It is **not** enough to fit a capacity ceiling with a usable confidence
  interval — 6 points, 4 of them clustered in a 42-hour stretch of one week, one
  a spend limit that is a different mechanism entirely. So: **build the fit
  against backfill, ship share-of-period as the displayed number until live
  hits accumulate**, exactly the fallback U3 names. The schedule compression is
  real but it lands on *development*, not on *calibration convergence*.
- **Consequences to carry forward:**
  - `collect/transcript.py` must not drop synthetic/zero-usage assistant
    records — they are the entire U3a signal.
  - `apiErrorStatus` and `error` belong in the Pydantic model; a limit-hit
    events table keyed off them is a Phase 1 deliverable, not Phase 3.
  - The other `error` values on disk are worth capturing too: `server_error`
    (28), `authentication_failed` (4), `oauth_org_not_allowed` (1),
    `invalid_request` (1). `server_error` at parity with `rate_limit` means the
    normaliser must not treat "an error record" as "a limit hit".
  - **3 of 29 hits are `isSidechain: true`** — subagents hit the ceiling too.
    Limit accounting is per-pool, not per-session (invariant 4, and U8).
  - `quotaLimits` appearing only on `2.1.245` is invariant 7 in miniature: the
    good field arrived in a point release. Record `version` on every limit-hit
    row so the fit knows which shape it is reading.

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

**Restructured 2026-09-09** around a decision: **get to a working end-to-end
solution, then improve it,** rather than resolving every unknown first. W1 made
that viable — there is deduplicated history on disk and a validated method for
reading it — and `U10` (#13) settled the one grain question that genuinely
blocked a slice. So the near milestones below are detailed and the later ones
deliberately loose; the further out they are, the more they depend on what the
slice teaches. **Don't add detail to M3–M5 speculatively.**

Numbering note: the old M1 (*reconcile within 2%*) became **M1′** and the old M2
(*Datasette*) folded into **M1**, because Datasette is the slice's UI rather than
a follow-on. Prior §5 rows referring to "M1" as reconciliation mean M1′.

### M0 · Phase 0 memo — **re-scoped** · [#10](https://github.com/francisbrero/Model-Use-Index/issues/10)
**Was:** U1–U7 each answered, plus a go/no-go on the allowance model.
**Now:** only what blocks the slice.

**Done when:**
- `U10` (#13) has a bounding rule — **done 2026-09-09**.
- `U2` is **accepted as a labelled bias, not resolved**: sidechain turns bill
  into the parent session, stated in the UI. #7 stays open.
- The golden-file fixtures TD §11 needs are collected, scrubbed and obviously
  synthetic (invariant 6).

**Deferred, still open, no longer gating:** `U1` (#6), `U3` (#8), `U5`, `U6`,
`U7`. Each is about live capture or a second provider, which a backfill-only
slice doesn't need — `U7` is outright moot for it, there being no OTel in the
loop. They return as M1′ and M2′. **The deferral is why M1 cannot claim
headroom.**

`U3a` (#5) was in this list; it is **answered 2026-09-09** and its answer does
not change the deferral. Limit hits *are* on disk, but 29 records are only **6
episodes** — enough to build the allowance model against, not enough to fit a
ceiling. So `U3` still gates headroom, and **M1 still cannot claim it.**

**Still a gate, for a narrower reason:** `W2` (#4) gates *committing to the
build*, so it runs before M1 — see §6. W1 demoted W2's 25% figure to a secondary
analysis, but the tier matrix stays load-bearing for *verdicts*, so W2 must land
before M1's steps 5–6. (`U3a` was the other gate; **answered 2026-09-09** — it
did not change the slice, since its go is qualified and M1 emits no headroom
figure either way.)

### M1 · First E2E slice — *the current centre of gravity* · [#14](https://github.com/francisbrero/Model-Use-Index/issues/14)
Backfill → dedup → work units → crude classifier → verdicts → Datasette.
**No hooks, no OTel, no `launchd`, no live tailer, no web app, no Codex, no
allowance model.**

**Why this cut.** W1 proved every step by hand, so this re-implements a validated
pipeline rather than discovering one. It is read-only over data already on disk,
so invariant 1 holds trivially — no hooks to wedge a turn. And it defers six of
eight unknowns to *after* something works.

**Build order** (each step verifiable on its own, TD §14):

1. **Skeleton** — `pyproject.toml` (uv, ruff, pytest), `config.toml.example`,
   `mui` typer stub.
2. **Schema** — `migrations/001_init.sql` against `schema_version`. Raw SQL, no
   ORM, no Alembic. SQLite at `~/.model-use-index/store.db`, WAL,
   `synchronous=NORMAL`, `busy_timeout=5000`.
3. **Backfill reader** — `collect/transcript.py`. Session id and content hash
   only; **no parsing, no Pydantic, no field extraction** (invariant 2).
4. **Dedup + work units** — `normalize/`. Dedup by `(message.id, requestId)`,
   **max per field** (invariant 10). Work units at `u10-next-anchor-v1`.
5. **Crude classifier** — `enrich/signals.py`. W1's six signals, deterministic,
   no LLM. **Blocked on the PRD emphasis pass** (§6): W1 concluded the taxonomy's
   top level should be kind-of-work, so coding this first builds the analysis W1
   showed was mis-aimed.
6. **Verdicts + Datasette** — `verdict.py` as pure functions (TD §11), then point
   Datasette at the file (TD §8.1). Also blocked on the emphasis pass, and on W2.

**Step 4 is the acceptance gate for the whole slice.** W1's and U10's figures are
the regression test — all *notional list value*:

| Target | Expected |
|---|---|
| Unique Opus API responses | 37,781 |
| Total Opus notional | $23,059 |
| Phoenix + worktrees share | 73.4% ($16,950) |
| `/release-prod`, 10 runs | **$1,447 ± 5%** — the rule's own output and the assertion |
| *(reference, not the assertion)* | $1,511 — W1's independent hand-read |
| Duplicate ratio | ~48% (34,314 / 72,083) |
| Arc overlap | **0** — asserted, not observed |
| Unattributable remainder | 7.4% ($1,730), a labelled row |

**Done when:** `mui backfill` is idempotent over real history; all step-4 figures
reproduce; Datasette shows work units faceted by score, repo and routine; and the
report surfaces at least one **category** (e.g. *agentic ops on Opus*) rather
than only the single offender W1 already found by hand.

**Two constraints that must not drift:**
- **No headroom claims.** `U3`/`U3a` are deferred, so headroom — the primary
  measure (invariant 5) — cannot be computed. Everything reads *notional list
  value*. A documented temporary deviation, not a redefinition.
- **Every number provisional.** The classifier is an unvalidated heuristic until
  M2′. Label it (R2) and **do not act on a figure from this slice.**

### M1′ · Live capture, then the first reconciled number
Hooks, `launchd`, the transcript tailer, the OTLP receiver — then the old M1 test:
Anthropic totals reconcile with `/usage` **within 2%** over a 7-day window,
reported by `mui doctor`.

**Done when:** that 2% holds, **and** `mui doctor` reports the duplicate ratio —
W1 showed a 91% overstatement is the likelier failure than a reconciliation gap,
and reconciliation alone would not catch it if both sides share a convention.

Picks up `U5`, `U6`, `U7`, and the invariant-1 hook-safety work the slice skipped.
This is where schema-drift and live-capture risk actually land.

### M2′ · Gold set and the real classifier
The named calendar day (R1), then `qwen3:4b` via Ollama replacing the crude
heuristic. Schema restated in the prompt text, concurrency 1 (invariant 7b).

**Done when:** ≥80% agreement with the gold set, `other` under 10%, and the
provisional labels come off the UI. **This is the gate before any number is
acted on.** Seed the labelling from W1's hand-read of the twelve most expensive
score-0 units — orchestration/CI shepherding is the boundary most easily got
wrong.

### M3 · First classified report — *loose*
**Done when:** the Model Use Index renders over validated classifications and
ranks **categories** by reclaimable headroom, with at least one the operator
agrees with on inspection.
Note the bar moved: W1 already produced a single finding by hand, so "one
finding" no longer tests anything. The category ranking does.

### M4 · First action taken — *loose; no useful date, protect the gap*
**Done when:** a default model or a routine's delegation is actually changed
because of what the tool said.
**Why it matters:** **this is where tools like this die** — not with a failure,
they just get opened less each week. Everything up to M3 is output; M4 is the
first behaviour change.
The `/release-prod` fix (§6) is a **manual dry run of M4** available now, needing
none of this tool.

### M5 · First verified action — *loose; one week after M4*
**Done when:** the predicted headroom either materialised or didn't, and the gap
is written down.
**Why it matters:** the only milestone that is an *outcome*, and the honest test
of R2. If you protect one thing in the schedule, protect M3 → M4 → M5.

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
| 2026-09-09 | **U10** | **Bounding rule: anchor → next anchor of any skill, else session end** (`u10-next-anchor-v1`). Reproduces `/release-prod` at **$1,447 notional list value over 10 runs** — W1's hand-read $1,511 within −4.2%. | **`work_unit` has a grain.** The first E2E slice is unblocked; the rule goes into `normalize/work_unit.py` asserting **$1,447 ± 5%** — the rule's own reproducible output (invariant 2b), with $1,511 kept as the separate hand-read reference. Centring on $1,511 ± 5% would exclude the $1,429 the accepted tail-cap variant produces. |
| 2026-09-09 | **U10** | **W1's own baseline was wrong at scale.** *Anchor → session end* double-counts **$13,118 of Opus notional list value**, because **110 of 137 anchored sessions carry more than one anchor** (median 2, max 9). Re-scored, it gives `/release-prod` $314, not $1,511. | W1's figure was right only because the release sessions were read by hand. **Overlap is the metric that separates these rules**, and it must be asserted as zero in the normaliser's tests. |
| 2026-09-09 | **U10** | **Idle-gap and `cwd`/`gitBranch` thresholds both fail.** Single `/release-prod` arcs legitimately contain gaps of 529, 699, 1,730 and **8,605 minutes** (waiting on CI, ArgoCD, review) and move across up to 47 turns of other branches. Idle-30 recovers 29% of target; context-change 69%. | **Do not add either as a boundary.** They cut the arc exactly where the routine is waiting or switching worktrees — both normal events *inside* an arc. Recorded so it isn't re-proposed. |
| 2026-09-09 | **U10** | Known error mode: the rule is **generous at the tail** — the last anchor absorbs to session end. Capping that arc at +150 turns moves `/release-prod` 1.2%; at +50 turns, 21%. | Accepted as-is; **don't cap tightly.** The generosity is bounded and the alternative loses more than it fixes. |
| 2026-09-09 | **U10** | **Unattributable remainder: 7.4% of Opus notional list value ($1,730)** — 6.0% ($1,415, 47 sessions) with no anchor, 1.3% ($315) pre-first-anchor. Sidechain turns are $1,966 (8.4%), $1,737 of it inside an arc. | Must be a **labelled dashboard row**, not dropped. Per-routine figures include subagent cost by construction — never also count it alongside (U8). |
| 2026-09-09 | **U10** | **Cross-session arcs unresolved.** 66 sessions end with the anchor tag still on the final turn. | Left open deliberately — Tier 2 for `work_unit`; the 7.4% remainder bounds how much it can matter. |
| 2026-09-09 | **Sequencing** | Decided: **get to a working E2E solution, then improve it**, rather than resolving every unknown first. Only `U10` blocked a backfill-only slice; `U1`/`U3`/`U3a`/`U5`/`U6`/`U7` are live-capture or second-provider questions, and `U7` is moot with no OTel in the loop. | **§3 restructured.** Old M1 (reconcile 2%) → **M1′**; old M2 (Datasette) folded into **M1** as the slice's UI; **M2′** added for the gold set. M3–M5 deliberately left loose. Slice scoped as #14. |
| 2026-09-09 | **Sequencing** | The first slice ships **no headroom figure** — deferring `U3`/`U3a` means the primary measure (invariant 5) can't be computed. | Accepted as a **documented temporary deviation**, not a redefinition: every slice figure reads *notional list value* and the UI must not imply share-of-allowance. |
| 2026-09-09 | **Sequencing** | The slice's classifier is a crude deterministic heuristic (W1's six signals), not Ollama. | Ships **labelled provisional** (R2); **no number from the slice is acted on** until M2′ clears the gold set. Keeps one unvalidated layer instead of two. |
| 2026-09-09 | **Process** | An agent asked to build #14 **correctly refused**, citing W2 and U3a as build gates — the issue had been created without updating §6, so the issue and the register disagreed. | **The register outranks an issue.** §6 now carries the full ordering *and* states that the gate falls between step 4 and step 5 of #14, since steps 1–4 carry no taxonomy or verdict logic. Both over- and under-reading of that gate have now happened once each. |
| 2026-09-09 | **U3a** | **Yes — limit hits are already on disk.** 29 `error: "rate_limit"` records, `apiErrorStatus: 429`, on synthetic zero-`usage` assistant messages (`message.model` is the literal `<synthetic>`); 16 sessions, 9 projects, 2026-07-30 → 2026-08-27. | **Backfill is worth running for allowance work.** `collect/transcript.py` must not filter out `<synthetic>` / zero-`usage` assistant records — they are the entire signal. They carry no tokens, so invariant 10 is unaffected. |
| 2026-09-09 | **U3a** | **29 records are only 6 episodes.** One limit event writes one record per *live* session — 8 records across 7 sessions inside four minutes on 2026-08-21. Breakdown: **4 session (5-hour), 1 weekly (7-day), 1 org monthly spend.** | **Dedupe limit hits by stated reset target, not by record**, or the allowance fit trains on the operator's parallelism instead of on the ceiling. A second dedup rule alongside invariant 10, on a different key. |
| 2026-09-09 | **U3a** | **A structured `quotaLimits` object exists — but only on client `2.1.245` (1 of 29).** `{status, resetsAt (unix epoch), rateLimitType: "seven_day", unifiedRateLimitFallbackAvailable, overageStatus, overageDisabledReason, isUsingOverage}`. The other 28 (`2.1.220`) carry the reset only as UI display text — local wall-clock, tz-named, no date on the 5-hour form. | **Key the allowance model on `quotaLimits`; parse text only as fallback.** Invariant 7 in miniature — the good field arrived in a point release, so record `version` on every limit-hit row. |
| 2026-09-09 | **U3a** | **Go/no-go: qualified go — backfill for the *shape*, live capture for the *fit*.** 6 boundary points, with 75–2,097 deduped assistant records in the 5h preceding each, is enough to build and sanity-check `enrich/allowance.py`; it is not enough to fit a ceiling with a usable interval (4 of 6 fall inside one 42-hour stretch, 1 is a spend limit — a different mechanism). | **Build the fit against backfill; display share-of-period until live hits accumulate** — `U3`'s stated fallback stands, and M1's no-headroom constraint is unchanged. The compression lands on *development*, not on calibration convergence. |
| 2026-09-09 | **U3a** | `rate_limit` (29) is at parity with `server_error` (28); also `authentication_failed` (4), `oauth_org_not_allowed` (1), `invalid_request` (1). **3 of 29 limit hits are `isSidechain: true`.** | The normaliser must not read "an error record" as "a limit hit" — capture `error` as an enum. Subagents hit the ceiling too, so limit accounting is **per-pool, not per-session** (invariant 4 · `U2`/`U8`). |
| 2026-09-09 | **W2** | **W2 cannot run as written — the Sonnet pool does not exist.** 3,730 Sonnet assistant records, but **3,652 (97.9%) are `isSidechain: true`** (subagent turns, one `subagents` directory). Only **78 main-agent records across 2 sessions**, both one-shot Q&A (`Retrieval / Low`), neither agentic. | **Method redesigned to Opus→Haiku** (operator call). Consequence carried forward: a Haiku failure means *"Haiku cannot do this"*, not *"Haiku is worse than Sonnet"* — so the cell may move to `mid` only after a confirming Sonnet run the history cannot supply. |
| 2026-09-09 | **W2** | **The `Agentic / Medium` band is 227 of 750 Phoenix work units, $3,887.59 notional list value**; median unit $12.55 / 18 tool calls / 32 turns. 150 have self-describing prompts; 77 are continuations (`ok`, `approved`) — real work, not restatable, kept in the denominator. | Pool is ample. Worklist of 20 candidates and 6 selected runs in [`phase0/w2-worklist.md`](../phase0/w2-worklist.md), with a **verdict rule fixed in advance** so the result isn't read to taste. |
| 2026-09-09 | **W2** | The band is dominated by `gh`, `git`, `argocd`, `kubectl`, `pnpm` — release orchestration and CI shepherding, often triggered by a one-word approval. | **Independent corroboration of W1's reframed headline** from a different filter over the same corpus: the volume in the cell under test *is* high-ceremony low-reasoning orchestration. |
| 2026-09-09 | **W2** | Mutating work had to be detected via **`Bash` verbs**, not `Edit`/`Write` — bypass-mode agents edit through `sed`/heredocs. An `Edit`-only filter would have mis-sized the band. | W1's false-positive trap recurred immediately in a second, unrelated analysis. Any taxonomy rule must classify `Bash` verbs; this is now twice-observed, not a one-off. |
| 2026-09-09 | **W2** | **The Opus control limits *both* verdict branches, not just failure.** Success shows Haiku handled tasks *selected from Opus-run history*, which may be Opus-shaped; failure shows Haiku is insufficient but never that `mid` is right. | Verdict table rewritten: a ≤2 result makes the cell **contested, not `mid`**, and **any PRD §8.1 edit is a separate PR** once evidence exists. An earlier draft told you to revise §8.1 *and* treat the result as unsettled — a contradiction, now removed. |
| 2026-09-09 | **W2** | All six selected tasks are release/CI orchestration. Representative of the band as it occurs, but narrower than the cell. | The result will speak to **agentic orchestration**, not to `Agentic / Medium` in full. Scope must be stated in the outcome row, or the test will be over-read. |
| 2026-09-09 | **W2** | Read-only partial runs (where no live equivalent exists) **cannot score `completed`** and are not on the same scale as full runs. | Scored separately as `assembled-correct`/`assembled-wrong` and reported apart from the completion tally; which tasks are read-only is decided **before** running, so the denominator isn't picked after seeing results. |
| 2026-09-09 | **Process** | The repo is **public**; the first worklist draft carried internal Jira ids, a release version and a service name. | De-identified to shapes; rows stay resolvable locally by date + cost + tool count. **Invariant 6 applies to analysis deliverables, not just fixtures and transcripts** — outcome rows must stay de-identified too. |

---

## 6. Next actions

1. ~~**W1**~~ ([#3](https://github.com/francisbrero/Model-Use-Index/issues/3))
   — the one-day spike. **Done 2026-09-09: go, reframed. 43.4% of Phoenix Opus
   value shows no complexity signal — release orchestration and CI shepherding
   on Opus. A4 is a strong second at 93% cache traffic.** See §1.
2. ~~**U3a**~~ ([#5](https://github.com/francisbrero/Model-Use-Index/issues/5))
   — **Done 2026-09-09: qualified go.** Limit hits *are* on disk, and a
   structured `quotaLimits` object exists on the newer client — but 29 records
   are only **6 distinct episodes**. Enough to build and sanity-check the
   allowance model now; **not** enough to fit a ceiling, so the displayed number
   stays share-of-period until live hits accumulate. M1's no-headroom constraint
   is unchanged. See §2.
3. **W2** ([#4](https://github.com/francisbrero/Model-Use-Index/issues/4)) —
   hand-test the `Agentic / Medium` hypothesis on Haiku. W1 lowered the stakes
   here — the 25% misallocation figure it defends is now a secondary analysis,
   not the headline — but it is still the cheapest way to find out whether the
   tier matrix is trustworthy at all, so it still runs before the build.
   **In progress: redesigned Opus→Haiku (no Sonnet pool exists), candidates
   selected, verdict rule fixed. Six hand-runs outstanding** — see
   [`phase0/w2-worklist.md`](../phase0/w2-worklist.md).
4. **The PRD emphasis pass** — A1 re-aimed at high-ceremony low-reasoning
   orchestration (not "trivial sessions"), A4 named as the second headline, and
   the taxonomy's top level set to *kind of work*. Queued behind W2.
5. **M1, the first E2E slice** ([#14](https://github.com/francisbrero/Model-Use-Index/issues/14))
   — see §3.

**`U10` is resolved out of band** ([#13](https://github.com/francisbrero/Model-Use-Index/issues/13),
answered 2026-09-09) — it was the only *unknown* blocking the first E2E slice, and
the slice's step-4 acceptance test now has a rule and a numeric target
(`/release-prod` = **$1,447 ± 5%** notional list value as the assertion, with W1's
$1,511 hand-read kept as the separate reference — see §2 U10 for why centring on
$1,511 would be self-contradictory).

**That unblocks the slice; it does not promote it ahead of W2**, which gates
committing to the build. Ordering decided 2026-09-09: run U3a, then W2, then the
emphasis pass, then #14 — **U3a is now done, so W2 is next.**

**Where the gate actually falls inside #14.** Steps 1–4 (skeleton, schema,
backfill, dedup, work units) contain no taxonomy and no verdict logic, so neither
W2 nor the emphasis pass can invalidate them. Steps 5–6 (classifier, verdicts)
depend on both. The gate is therefore **between step 4 and step 5** — recorded
because reading it as a blanket gate on all six steps is stricter than the
evidence supports, and reading it as no gate at all builds an analysis W1 already
showed was mis-aimed. Both misreadings have happened.

Do not fix the deferred Phase 0 scope until the emphasis pass lands.

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
| `U3a` | [#5](https://github.com/francisbrero/Model-Use-Index/issues/5) | Tier 1 | **answered 2026-09-09** |
| `U10` | [#13](https://github.com/francisbrero/Model-Use-Index/issues/13) | Tier 1 — **slice blocker** | **answered 2026-09-09** |
| `U1` | [#6](https://github.com/francisbrero/Model-Use-Index/issues/6) | Tier 1 | open |
| `U2` | [#7](https://github.com/francisbrero/Model-Use-Index/issues/7) | Tier 1 | open |
| `U3` | [#8](https://github.com/francisbrero/Model-Use-Index/issues/8) | Tier 1 | open |
| `U4` | [#9](https://github.com/francisbrero/Model-Use-Index/issues/9) | Tier 1 | **answered incidentally by W1** (U4REF) — close #9 against §5 |
| `M1` | [#14](https://github.com/francisbrero/Model-Use-Index/issues/14) | Milestone — the E2E slice | open, gated (see §6) |
| `M0` | [#10](https://github.com/francisbrero/Model-Use-Index/issues/10) | Milestone | open |

Tier 2 (`U5`–`U7`) is tracked on the M0 checklist rather than as separate issues;
Tier 3 (`U8`, `U9`) gets an issue when its phase opens. **W1 rehearsed `U8`** —
sidechain turns bill to the parent session — so that issue should carry the
rehearsal note when it opens.
