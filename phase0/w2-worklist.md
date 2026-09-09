# W2 — Agentic/Medium hand-test worklist

**Status: ready to run. Generated 2026-09-09. Issue [#4](https://github.com/francisbrero/Model-Use-Index/issues/4).**

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

Ranked by notional list value. `#` marks the six selected for hand-running.

| # | $ | Tools | Turns | Date | Task |
|---|---|---|---|---|---|
| ★1 | 57.32 | 36 | 57 | 08-04 | fix 1989 and update DVO 3504 to be about both staging and prod |
| ★2 | 55.89 | 35 | 70 | 08-21 | merge the PRs in order |
| 3 | 48.39 | 38 | 79 | 08-19 | PR was merged, please go through the steps |
| ★4 | 48.14 | 27 | 54 | 08-14 | merge and run the staging test |
| ★5 | 46.82 | 37 | 67 | 08-28 | address the concerns raised by the devops internal bot |
| 6 | 46.33 | 15 | 30 | 08-24 | it's been approved, merge and let me know when I can test |
| 7 | 41.41 | 26 | 58 | 08-21 | 3961 is accepted (and actually merged) |
| ★8 | 39.06 | 24 | 45 | 08-14 | publish v1.1.14, open the prod newTag bump PR, file two AC amendments + index follow-up as issues |
| 9 | 37.88 | 31 | 56 | 08-03 | merge and let me know when we can run the staging test |
| 10 | 36.40 | 48 | 90 | 08-22 | merge and test on staging e2e |
| 11 | 34.73 | 19 | 32 | 09-02 | check if this has been promoted to prod and then run the scripts |
| ★12 | 34.41 | 42 | 75 | 08-21 | add the agent-service-canary to this PR — same structural gap |
| 13 | 33.27 | 31 | 55 | 08-15 | check where we're at today |
| 14 | 32.30 | 17 | 36 | 09-01 | (deploy triage) — you can likely do it yourself |
| 15 | 29.72 | 17 | 34 | 08-30 | run it since you'd have me run the same commands anyway |
| 16 | 81.16 | 12 | 27 | 08-04 | Directory (Tenant) ID unclaimed — credential not saved, retry |
| 17 | 66.60 | 40 | 73 | 08-21 | back-of-envelope credit modelling for ent rep account briefs |
| 18 | 47.71 | 25 | 40 | 08-04 | single-tenant vs multi-tenant in customer-facing UI |
| 19 | 45.09 | 43 | 68 | 08-25 | strip internal copy, run humanizer, ask Codex to critique |
| 20 | 32.96 | 24 | 42 | 08-25 | jira-to-github-issue workflow gap — "runs where your reps are" |

**16–20 are deliberately listed but not selected.** 16 is an auth-credential
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
| 1 | fix 1989 + update DVO 3504 for staging and prod | $57.32 | Both Jira issues updated correctly; scope of 3504 covers both envs |
| 2 | merge the PRs in order | $55.89 | Dependency order respected; no merge run out of sequence |
| 4 | merge and run the staging test | $48.14 | Merge lands, staging suite invoked, result read back correctly |
| 5 | address devops bot concerns | $46.82 | Each bot comment resolved or answered; no fabricated resolution |
| 8 | publish v1.1.14 + prod newTag PR + file 3 issues | $39.06 | Release published, bump PR open, all three issues filed |
| 12 | add agent-service-canary to the PR | $34.41 | Canary added matching the existing structural pattern |

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

| Outcome across the six | Verdict on `Agentic / Medium` |
|---|---|
| ≥5 complete (retries ok), no cost blow-up | **Keep `small`.** Cell survives. |
| 3–4 complete | **Keep `small`, flag for M2′ gold set.** Weak but not refuted. |
| ≤2 complete, **or** ≥3 need retries costing >2× the Opus turn count | **Change to `mid`**, revise PRD §8.1, and re-derive the 25% figure. Pending a Sonnet confirmation before `mid` is treated as settled. |

If the cell changes, PRD §8.1 and every figure derived from it are updated in the
same PR (issue #4's own done-condition).
