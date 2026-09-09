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
| `U1` | [#6](https://github.com/francisbrero/Model-Use-Index/issues/6) | Tier 1 | open |
| `U2` | [#7](https://github.com/francisbrero/Model-Use-Index/issues/7) | Tier 1 | open |
| `U3` | [#8](https://github.com/francisbrero/Model-Use-Index/issues/8) | Tier 1 | open |
| `U4` | [#9](https://github.com/francisbrero/Model-Use-Index/issues/9) | Tier 1 | **answered incidentally by W1** (U4REF) |
| `M0` | [#10](https://github.com/francisbrero/Model-Use-Index/issues/10) | Milestone | open |

Tier 2 (`U5`–`U7`) is tracked on the M0 checklist rather than as separate issues;
Tier 3 (`U8`, `U9`) gets an issue when its phase opens. **W1 rehearsed `U8`** —
sidechain turns bill to the parent session — so that issue should carry the
rehearsal note when it opens.
