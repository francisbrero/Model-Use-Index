Fetch GitHub issue `$ARGUMENTS` and implement it end to end.

## Step 0 — Session resume detection

Before starting fresh, check whether dev docs already exist:

```
if dev/active/issue-{number}/ exists:
  Read context.md for the last checkpoint
  Resume from the last completed step; skip what's done
```

## Step 1 — Fetch the issue and branch

- `gh issue view $ARGUMENTS --json title,body,labels,assignees`
- Parse labels for the branch prefix (`feature/`, `bugfix/`, `chore/`)
- `git checkout -b {prefix}/issue-{number}-{slug}`

## Step 2 — Clarify requirements

Parse the issue body for ambiguity. Use `AskUserQuestion` to resolve anything
unclear **before** planning, and record the answers in `context.md`.

For this project specifically, check whether the issue depends on a Phase 0
finding that isn't settled yet (subagent on-disk layout, Codex log location and
token counts, whether allowance is readable or must be modelled,
`OTEL_LOG_RAW_API_BODIES`, transcript-vs-OTel agreement, which hooks fire — PRD
§14). If it does and the finding isn't in `phase0/findings.md`, say so and stop.
Building on an unsettled assumption is the failure mode Phase 0 exists to prevent.

## Step 3 — Create dev docs

Create `dev/active/issue-{number}/` with `plan.md`, `context.md`, `tasks.md`.

**`plan.md`** — Issue / Approach / Phases / Key Decisions.
**`context.md`** — Current Step / Key Files / Review Rounds / Next Steps.
**`tasks.md`** — the task list with dependencies.

`dev/` is gitignored; these are local working notes.

## Step 4 — Plan

Break the issue into phases. Use `TaskCreate` for progress tracking, with
`blockedBy` relationships where phases depend on each other.

**Search delegation:** targeted lookups (known path or symbol) stay in the main
context with `Read`/`grep`. Open-ended exploration ("where does X live", "find
callers of Y") goes to an `Explore` subagent on Haiku. Don't grep broadly in the
main session.

Re-read the relevant PRD section before planning — `sed -n` the section, don't
read all 1200 lines.

## Step 5 — Plan review loop

```
ROUND=1
while ROUND <= 10:
  Launch plan-reviewer subagent
  Record round + findings in context.md
  if MATERIAL_FINDINGS: false → break
  else → address findings; ROUND++
```

## Step 6 — Implement

Implement each phase. Update `context.md` as you go so a resumed session picks
up cleanly.

## Step 7 — Test and code review loop

- Run the tests (`uv run pytest`). **Tests must pass before marking complete.**
- Then:

```
ROUND=1
while ROUND <= 10:
  Launch code-reviewer subagent
  Record round + findings in context.md
  if MATERIAL_FINDINGS: false → break
  else → fix; ROUND++
```

## Step 8 — Create the PR

Use `/create-pr` (reads the template, runs the captured-data and invariant
checks). Link the original issue.

## Step 9 — Impact readout (non-gating)

Run the `pr-impact-reviewer` subagent and post its output as a PR comment. This
step **never blocks** — on any failure, note it and finish anyway.
