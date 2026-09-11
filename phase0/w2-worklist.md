# W2 — Agentic/Medium hand-test worklist

> **SUPERSEDED 2026-09-10 — W2 is moot; do not work this list.**
> A two-run pilot (below) completed both tasks on Haiku with zero corrections,
> but found the tier matrix's unit of account incomplete: reviewer subagents run
> on **Opus** at **5.9× the worker's cost**, so a per-unit verdict cannot say
> what a downgrade saves. The cell is settled by **M2′'s gold set + U9's outcome
> data** instead. Kept for the method and the band analysis, both of which stand.

**Generated 2026-09-09. Issue [#4](https://github.com/francisbrero/Model-Use-Index/issues/4).**

---

## Pilot results (2026-09-10) — `W2-pilot`, n=2, not the six

Live tasks the operator needed anyway, run on Haiku in separate sessions.
Both **completed with zero corrections** — the two operator messages were a
workflow gate answer and scope he'd have given Opus too.

| Run | Band | Tools / turns | Outcome | Haiku | If Opus |
|---|---|---|---|---|---|
| `/jira-to-github` on one ticket | in band | 53 / 79 | **completed** — issue filed, Jira linked | $0.49 | $7.36 |
| `/fix-issue` on that issue | **out of band** | 107 / 182 | **completed** — PR opened, required CI green | $1.15 | $17.31 |

All figures **notional list value**, deduped by `(message.id, requestId)`
max-per-field, four token fields priced separately.

**Two self-corrections in run 1**, both recovered without the operator: a wrong
issue label (`documentation` → discovered `docs` via `gh label list`) and a wrong
`jira comment` flag. That is the `Agentic` definition's error-recovery actually
happening.

### The finding that closed W2

**Run 2's saving was not 15×.** Its three reviewer subagents — `plan-reviewer`,
`pr-impact-reviewer`, `code-reviewer` — **all ran on Opus**, because a subagent's
model comes from its agent definition, not the session's `--model`:

| | Notional list value |
|---|---|
| Haiku worker | $1.15 |
| **Opus reviewers** | **$6.80** |
| **True total** | **$7.96** |

Reviewers are **85.5% of run cost, 5.9× the worker**; the real saving against
all-Opus is **2.2×**. The completion still belongs to Haiku — the reviewers
reviewed, and Haiku made the fix commit itself — but **the tier matrix scores a
work unit while a routine's cost is worker + reviewers**, and it has no way to
express *worker `small`, reviewers `frontier`*. That gap survives whatever the
cell's value turns out to be, which is why six more hand-runs were not the right
next spend.

**Open, unverified:** the runbook's task list named Codex plan/code reviews, but
the transcript shows only Claude subagents. If Codex also reviewed, that is
Source E1, invisible to this accounting, and a **second pool** — never summed
(invariant 4).

This is the input to W2, not its answer. The answer is six hand-run outcomes,
recorded in §5 of `milestones.md`.

---

## The design changed, and why

W2 as written says: *pick 20 recent `Agentic / Medium` tasks that were run on
**Sonnet**, re-run five or six on Haiku.* **That pool does not exist.**

| Model | Assistant records | Note |
|---|---|---|
| `claude-opus-5` | 75,282 | |
| `claude-haiku-4-5` | 4,564 | |
| `claude-sonnet-5` | 2,502 | |
| `claude-sonnet-4-6` | 1,228 | |

Sonnet totals 3,730 records, but **3,652 (97.9%) are `isSidechain: true`** —
subagent turns, all inside one `subagents` project directory. Those are delegated
searches under an Opus parent, with no independently observed outcome; their
success says the Explore agent found files, not that agentic work completes on a
small model.

**Exactly 78 main-agent Sonnet records exist, across 2 sessions.** Both are
one-shot Q&A — a security-questionnaire read (explicitly *"don't make any
changes"*) and a support question about undoing a declined invite. Neither is
`Agentic / Medium`; both are closer to `Retrieval / Low`.

**So the control changes from Sonnet to Opus** (operator decision, 2026-09-09).
This has a consequence that must be carried into the verdict: a Haiku failure now
means *"Haiku cannot do this"*, **not** *"Haiku is worse than Sonnet at this."*
The test still falsifies the `Agentic / Medium → small` cell — `small` is the
Haiku tier, and that cell is precisely the claim that a small model suffices —
but it cannot distinguish `small` from `mid`. **If Haiku fails, the cell should
move to `mid` only after a confirming Sonnet run**, which the history cannot
supply and a fresh run would have to.

---

## How the pool was built

Phoenix + worktrees only (73.4% of Opus value, W1). Work units segmented at
main-agent user prompts, deduplicated by `(message.id, requestId)` with max-per-
field (invariant 10), priced at Opus list rates as **notional list value**
(invariant 5).

- 750 work units → **227 in the Agentic/Medium band, $3,887.59 notional list value.**
- Band filter: ≥4 tool calls; ≥2 mutating operations (`Edit`/`Write` or a
  mutating `Bash` verb — `git`, `gh`, `pnpm`, `kubectl`, `argocd`, `sed`, …,
  since bypass-mode agents edit through `Bash`, W1's false-positive trap);
  6–60 tool calls and ≤90 turns to exclude Low (single-step) and High (sprawling).
- Median unit: **$12.55, 18 tool calls, 32 turns.**
- 150 of the 227 have self-describing prompts. The other 77 are continuations
  (`ok`, `yes`, `approved`) — real work, but not restatable as an instruction, so
  they are excluded from the run list and kept in the denominator.

The band's shape corroborates W1 independently: it is dominated by `gh`, `git`,
`argocd`, `kubectl` and `pnpm` — release orchestration and CI shepherding,
frequently triggered by a one-word approval.

---

## The 20 candidates

**Rows 1–15 are the in-band candidates, ranked by notional list value. Rows
16–20 are a separate out-of-band group** (see the note under the table) and are
*not* in that ranking — which is why row 16 restarts at $81.16. `★` marks the six
selected for hand-running.

| # | $ | Tools | Turns | Date | Task |
|---|---|---|---|---|---|
| ★1 | 57.32 | 36 | 57 | 08-04 | fix one Jira issue and re-scope a second to cover both staging and prod |
| ★2 | 55.89 | 35 | 70 | 08-21 | merge the PRs in order |
| 3 | 48.39 | 38 | 79 | 08-19 | PR was merged, please go through the steps |
| ★4 | 48.14 | 27 | 54 | 08-14 | merge and run the staging test |
| ★5 | 46.82 | 37 | 67 | 08-28 | address the concerns raised by the devops internal bot |
| 6 | 46.33 | 15 | 30 | 08-24 | it's been approved, merge and let me know when I can test |
| 7 | 41.41 | 26 | 58 | 08-21 | a named PR is accepted and merged — carry out the follow-through |
| ★8 | 39.06 | 24 | 45 | 08-14 | publish a patch release, open the prod newTag bump PR, file three follow-up issues |
| 9 | 37.88 | 31 | 56 | 08-03 | merge and let me know when we can run the staging test |
| 10 | 36.40 | 48 | 90 | 08-22 | merge and test on staging e2e |
| 11 | 34.73 | 19 | 32 | 09-02 | check if this has been promoted to prod and then run the scripts |
| ★12 | 34.41 | 42 | 75 | 08-21 | add a second service's canary to an open PR — same structural gap |
| 13 | 33.27 | 31 | 55 | 08-15 | check where we're at today |
| 14 | 32.30 | 17 | 36 | 09-01 | (deploy triage) — you can likely do it yourself |
| 15 | 29.72 | 17 | 34 | 08-30 | run it since you'd have me run the same commands anyway |
| 16 | 81.16 | 12 | 27 | 08-04 | Directory (Tenant) ID unclaimed — credential not saved, retry |
| 17 | 66.60 | 40 | 73 | 08-21 | back-of-envelope credit modelling for ent rep account briefs |
| 18 | 47.71 | 25 | 40 | 08-04 | single-tenant vs multi-tenant in customer-facing UI |
| 19 | 45.09 | 43 | 68 | 08-25 | strip internal copy, run humanizer, ask Codex to critique |
| 20 | 32.96 | 24 | 42 | 08-25 | a gap in the issue-tracker-to-GitHub workflow step |

> **Descriptions are deliberately de-identified — this repository is public.**
> Internal ticket numbers, release versions and service names are replaced with
> their shape ("one Jira issue", "a patch release", "a second service's canary").
> Each row is unambiguous against your local history by date + cost + tool count;
> resolve the specifics from the transcript when you run it, and **keep them out
> of the outcome rows you write into `milestones.md`** (invariant 6).

**16–20 are out of band: deliberately listed, not candidates.** 16 is an auth-credential
loop (mostly waiting on an external system), 17 is `Reasoning` not `Agentic`,
and 18–20 are `Synthesis`. They are here so the boundary of the band is visible
and so the six selections aren't mistaken for the whole pool.

---

## The six to run

Chosen for: unambiguous restatable instruction, genuine multi-step tool
execution, and a **verifiable landing condition** — you can tell whether it
worked without a judgement call.

| ★ | Task | Opus cost | Lands when |
|---|---|---|---|
| 1 | fix one Jira issue, re-scope a second for staging and prod | $57.32 | Both issues updated correctly; the re-scoped one covers both envs |
| 2 | merge the PRs in order | $55.89 | Dependency order respected; no merge run out of sequence |
| 4 | merge and run the staging test | $48.14 | Merge lands, staging suite invoked, result read back correctly |
| 5 | address devops bot concerns | $46.82 | Each bot comment resolved or answered; no fabricated resolution |
| 8 | publish a patch release + prod newTag PR + file 3 issues | $39.06 | Release published, bump PR open, all three issues filed |
| 12 | add a second service's canary to the PR | $34.41 | Canary added matching the existing structural pattern |

**Total: $281.64** notional list value at Opus — a useful secondary datapoint,
since it is the cost of six units in the band the matrix claims should be `small`.

### Running them

Re-run on Haiku against **equivalent current state**, not the original state —
these mutate real systems, and re-merging an already-merged PR tests nothing.
Point each at a live equivalent (an open PR awaiting merge, a current bot
comment thread). Where no live equivalent exists, run it read-only up to the
mutating step and judge whether the agent had assembled the correct action.

**Do not** re-run 8 or 4 against production for the sake of the experiment.

### Record per task

```
task · outcome{completed | completed-with-retries | failed} · turns · notional $
      · what broke, if anything
```

`completed-with-retries` is the load-bearing category — it is what
distinguishes "Haiku can do this" from "Haiku can do this **cheaply**", and R2
says the headroom estimate assumes the cheaper model finishes in the same tokens.
**Record turns and cost even on success**; a task that lands in 3× the turns
partially refutes the cell even though it "worked."

---

## Verdict rule, fixed in advance

Fix this before running, so the result isn't read to taste:

**Cost blow-up** means a task's Haiku run exceeds **2× the recorded Opus turn
count** for that task. It is the only cost guard, and it applies to *every* row
below, not just the failure row — R2's whole point is that a task landing in 3×
the turns has not demonstrated reclaimable headroom.

| Outcome across the six | Verdict on `Agentic / Medium` |
|---|---|
| ≥5 complete, no cost blow-up | **`small` survives this test** — but see the ceiling below. Do not restate it as confirmed. |
| 3–4 complete, **or** ≥5 complete with ≥3 blowing up on cost | **Inconclusive. Keep `small`, flag for M2′ gold set.** Weak but not refuted. |
| ≤2 complete | **`small` is refuted for this band.** Record the finding; **do not edit PRD §8.1 yet** — see below. |

### What this test can and cannot settle

**Both branches are limited by the Opus control, not just the failure branch.**

- **On failure:** the test shows Haiku is insufficient. It does **not** show
  `mid` is correct — that requires a Sonnet run this history cannot supply. So a
  ≤2 result **does not by itself change the matrix.** It downgrades
  `Agentic / Medium` to *contested*, and the cell moves to `mid` only after a
  confirming Sonnet run. **This resolves the contradiction in an earlier draft of
  this table, which told you to revise PRD §8.1 and to treat the result as
  unsettled in the same breath.**
- **On success:** the test shows Haiku handled six tasks *selected from
  Opus-run history*. Those tasks were shaped by what the operator chose to give
  Opus, so they may be Opus-shaped in ways that flatter or penalise Haiku
  unpredictably. `small` surviving is **evidence for the cell, not confirmation
  of it.**
- **Generalisation is narrower than the cell.** All six selected tasks are
  release/CI orchestration (`merge`, `publish`, `argocd`). That is representative
  of *this band as it actually occurs* — which is the point — but the result
  speaks to **agentic orchestration**, not to `Agentic / Medium` in full. State
  that scope in the outcome row.
- **n=6 is small.** Nothing here produces a confidence interval. This test is
  built to catch a cell that is *badly* wrong, not to fine-tune one.

### Scoring partial runs

Tasks with no live equivalent are run read-only up to the mutating step. **A
read-only run can never score `completed`** — it is not on the same scale as a
full run. Score it separately as `assembled-correct` / `assembled-wrong`
(did the agent have the right action staged?) and **report those counts apart
from the completion tally.** Decide which tasks are read-only *before* running,
so the denominator isn't chosen after seeing results.

**Any PRD §8.1 edit is a separate PR** with the outcomes attached, not a
side-effect of this one. Issue #4's done-condition — *"if the cell changes,
§8.1 and any figure derived from it are updated in the same PR"* — is satisfied
by that PR, since the cell does not change until the evidence is in hand.
