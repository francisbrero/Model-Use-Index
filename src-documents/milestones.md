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

### W1 — The one-day spike *(status: open · [#3](https://github.com/francisbrero/Model-Use-Index/issues/3))*

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
| | | | |

---

## 6. Next three actions

1. **W1** ([#3](https://github.com/francisbrero/Model-Use-Index/issues/3)) — the
   one-day spike. Does the finding exist at all?
2. **W2** ([#4](https://github.com/francisbrero/Model-Use-Index/issues/4)) —
   hand-test the `Agentic / Medium` hypothesis on Haiku.
3. **U3a** ([#5](https://github.com/francisbrero/Model-Use-Index/issues/5)) — grep
   existing history for past rate-limit errors. Twenty minutes, and it may save
   six weeks of waiting for calibration data.

Everything else waits on these three.

### Issue tracking

The week-one gates and the Tier 1 unknowns are tracked as GitHub issues; **this
document stays the source of truth for the answers.** Record each answer here
(inline, then §5) and close the issue against it — don't let the issue thread
become the register.

| Register ID | Issue | Tier |
|---|---|---|
| `W1` | [#3](https://github.com/francisbrero/Model-Use-Index/issues/3) | Week one — gate |
| `W2` | [#4](https://github.com/francisbrero/Model-Use-Index/issues/4) | Week one — gate |
| `U3a` | [#5](https://github.com/francisbrero/Model-Use-Index/issues/5) | Tier 1 |
| `U1` | [#6](https://github.com/francisbrero/Model-Use-Index/issues/6) | Tier 1 |
| `U2` | [#7](https://github.com/francisbrero/Model-Use-Index/issues/7) | Tier 1 |
| `U3` | [#8](https://github.com/francisbrero/Model-Use-Index/issues/8) | Tier 1 |
| `U4` | [#9](https://github.com/francisbrero/Model-Use-Index/issues/9) | Tier 1 |
| `M0` | [#10](https://github.com/francisbrero/Model-Use-Index/issues/10) | Milestone |

Tier 2 (`U5`–`U7`) is tracked on the M0 checklist rather than as separate issues;
Tier 3 (`U8`, `U9`) gets an issue when its phase opens.