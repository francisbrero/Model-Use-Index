# Phase 0 — Reconnaissance

Investigation only. No production code lands from this phase.

`findings.md` is the deliverable: six questions, each answered with a sample
record and its consequence for the design (PRD §14).

## Privacy

`phase0/**` is gitignored except this file, `findings.md` and
`w2-worklist.md`. Sample records off the machine contain real prompts, paths and
shell commands — keep them local. Anything pasted into a tracked file here must
be scrubbed and obviously synthetic.

`w2-worklist.md` is the exception's one instance: W2 is a **week-one gate**, not
one of Phase 0's six questions, so it does not belong in `findings.md` — but it
is a scrubbed deliverable (task descriptions reduced to verbs and identifiers, no
paths, hostnames or session ids) that the hand-runs are executed against, so it
is reviewable in git. Add further exceptions only on the same terms.

## Why this phase exists

Six assumptions currently sit under the Phase 1 design. Each one, if wrong,
produces a system that reports confident numbers that are quietly incorrect —
misattributed subagent consumption, invisible Codex spend making delegated rows
look cheap, a fitted allowance model where a direct read was available. Cheaper
to spend two days here than to rebuild Phase 1 on a corrected assumption.
