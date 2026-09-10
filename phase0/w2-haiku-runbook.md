# W2 — Haiku run protocol (live task, n=1)

**Generated 2026-09-10. Companion to [`w2-worklist.md`](w2-worklist.md). Issue [#4](https://github.com/francisbrero/Model-Use-Index/issues/4).**

---

## What this run is and isn't

You are running **a real Phoenix task you need done anyway**, on Haiku, in a
separate session. That is better than the worklist's design in one respect: no
"re-run against equivalent state" contortion, because the state is live.

**But it is a task of convenience, not a sample from the band.** The worklist's
verdict table needs six tasks drawn from `Agentic / Medium` *as it actually
occurs*. This is n=1, self-selected.

| This run can | This run cannot |
|---|---|
| Show Haiku handles (or fails) one in-band agentic task, with turn and cost data | Move the `Agentic / Medium` cell either way |
| Catch a *badly* wrong cell — if Haiku falls over on something you'd call simple, that's a real signal | Be scored against the verdict table as one of the six |
| Calibrate what `completed-with-retries` looks like in practice, before the real six | Distinguish `small` from `mid` (Opus control problem — unchanged) |

Record it as **`W2-pilot`**, not as W2 run 1/6.

---

## Before you start

**Confirm the task is in band.** From the worklist's filter:

- [ ] Multi-step against real state — edits files, or runs `git` / `gh` / `pnpm` / `kubectl` / `argocd`
- [ ] **≥2 mutating operations** (an `Edit`/`Write`, or a mutating `Bash` verb)
- [ ] Plausibly **6–60 tool calls** — if you'd guess "two commands", it's `Low`, out of band
- [ ] Not a design/diagnosis task — that's `Reasoning` or `High`, where the matrix expects frontier anyway
- [ ] You can state a **verifiable landing condition** *before* running: write down now what "done correctly" means

If it fails the ≥2-mutating or 6–60 test, run it anyway for your own sake — just
don't record it as a W2 datapoint.

**Write the landing condition down first.** One line, in the log block at the
bottom. Deciding "did it land" after watching it work is how this test gets read
to taste — the same failure the worklist's fixed verdict rule exists to prevent.

---

## Setup

Separate session, so the transcript is clean and attributable:

```sh
cd ~/Documents/MadKudu/Phoenix          # or the worktree the task belongs in
claude --model claude-haiku-4-5-20251001
```

Then confirm the model actually took, because a silent fallback to Opus
invalidates the whole run:

```
/status
```

It must read Haiku. **If it says Opus or Sonnet, stop** — the run is worthless as
a datapoint. (I can also verify this from the transcript afterward, and will.)

### Keep it comparable

The band's Opus baseline was measured on your normal harness, so change nothing
else:

- **Don't** thin your `CLAUDE.md`, skills, or hooks to "give Haiku a fair chance."
  Prompt-engineering the run measures your patience, not the model.
- **Don't** pre-decompose the task into steps. Give it the instruction you'd have
  given Opus — one prompt, as you'd normally phrase it. The cell's claim is that
  medium agentic work is *mechanical enough* that a cheap model with good tools
  handles it. Hand-holding tests the opposite claim.
- **Do** answer its questions as you normally would.

---

## While it runs — the one judgement call

Everything else I can recover from the transcript. This one I can't:

**Count your interventions.** Every time you correct it, redirect it, or supply
something it should have found — tally it. A tally of 0 versus 6 is the whole
difference between `completed` and `completed-with-retries`, and the transcript
shows *that* you typed, never *why*.

Stop conditions, decided now rather than in the moment:

| Stop when | Score it |
|---|---|
| Landing condition met | `completed` (with your intervention count) |
| Met, but you intervened ≥3 times or it burned obvious extra turns | `completed-with-retries` |
| It's about to do something destructive or wrong on real infra | `failed` — and say what it was about to do |
| ~15 minutes past where Opus would have finished | `failed` (timeout) |

**Do not rescue it into success.** If you find yourself doing the task through
it, that's `failed`, and it's a more informative result than a rescued pass.

---

## After — I measure it

Tell me it's done and I'll pull from the transcript, using the same accounting as
the band baseline (dedup by `(message.id, requestId)` max-per-field, all four
token fields priced separately, **notional list value**):

- model actually used (the fallback check)
- tool calls, mutating ops, turns
- Haiku notional list value, and the same work priced at Opus rates for contrast
- whether it lands in the 6–60 / ≤90 band

You supply: **landing condition met? intervention count? what broke?**

---

## Log block — fill this in

```
W2-pilot
  task (one line, de-identified — the repo is public):
  landing condition, written BEFORE running:

  model confirmed via /status:
  interventions (your tally):
  outcome: completed | completed-with-retries | failed
  what broke, if anything:
  would you have shipped this result:
```

Keep internal ticket ids, service names and versions out of the line you give me
for the register — invariant 6 covers analysis deliverables, and this repo is
public.
