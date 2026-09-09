# Anchor-shape fixtures — U10

**Synthetic. Hand-written. Not scrubbed real data** (invariant 6, TD §11).

Session ids are `SYNTH-*`, paths are `/synthetic/repo`, message ids are
`msg_synth_*`. No real prompt text, file path, shell command or session id
appears here. Token counts are round numbers chosen to make the expected
attribution arithmetic checkable by hand.

`anchor_shapes.jsonl` encodes the five shapes U10 characterised, one session
each. `expected.json` gives, per session, the arc boundaries **and** the Opus
**notional list value** of each arc, of the unattributable remainder, of the
sidechain value falling inside an arc, and of the session total — everything
`normalize/work_unit.py` must reproduce under the U10 rule (*anchor → next
anchor of any skill, else session end*).

The dollar figures use the rate table in `expected.json`
(`rates_version: synthetic-fixture-v1`), not production rates. It preserves the
only thing that has to hold — the *relative* structure of the four fields
(`output` 5× input, `cache_write` 1.25×, `cache_read` 0.1×) — so pricing
`cache_read` at the input rate, a 10× error on the largest real line item,
fails a test rather than passing quietly.

| Session | Shape | Why it is here |
|---|---|---|
| `SYNTH-single` | one anchor, work continues after the tag | the base case — the tag undercounts, the arc does not |
| `SYNTH-two-distinct` | two anchors, different skills | the boundary case the rule exists for |
| `SYNTH-two-same` | same skill invoked twice | re-invocation is a boundary, not a merge |
| `SYNTH-pre-anchor` | untagged work before the first anchor | must land in the unattributable remainder |
| `SYNTH-idle-gap` | a 6-day gap *inside* one arc | the case that kills an idle-time threshold |
| `SYNTH-tag-hole` | one skill, tagged either side of an untagged turn | a hole fragments the arc — accepted, but pinned so it can't change silently |
| `SYNTH-long-run-then-anchor` | a **3-turn** anchor run, then a second anchor | the only session where the next run's `start` and `tag_end` differ |
| `SYNTH-out-of-order` | records written non-chronologically | order is part of the rule, not of the file layout |
| `SYNTH-no-anchor` | no anchor anywhere | the largest remainder component — 6.0% of Opus value at full scale |
| `SYNTH-adjacent-anchors` | two runs with no gap between them | a run-advance off-by-one would drop a whole arc |
| `SYNTH-dup-and-tie` | a dup group written **high-then-low**, plus tied timestamps | kills last-by-file-order, and pins the tie-break |

`SYNTH-dup-and-tie` is the mirror of `SYNTH-idle-gap`: that group is written
500 then 2,000, where last-by-file-order happens to *equal* max, so it cannot
tell the two reductions apart. This one is written 2,000 / 500 / 900, where max
is 2,000 and last-wins would be 900. Invariant 10 rejects both first-seen and
last-by-file-order, so it takes one group in each direction to hold that.

`SYNTH-long-run-then-anchor` is the one that matters most. Everywhere else a
non-final anchor run is one turn long, so `start == tag_end` and a boundary
computed from the wrong one of the two is invisible. Real anchor runs are median
15 turns (p90 36, max 272), so a multi-turn run followed by another anchor is the
*normal* shape — and it is the shape that distinguishes a correct boundary from
one that claims turns twice.

The last row is the load-bearing one: a release routine waiting on CI produces
gaps of hours to days, so a gap is not evidence the arc ended. It also carries a
duplicate content-block record whose `output_tokens` differ (500 then 2,000) and
a sidechain turn inside the arc, so the fixture exercises the invariant-10 dedup
and U8 sidechain traps as well as the boundary rule.

`tests/test_anchor_arc.py` consumes all of it, and implements the **rejected**
candidate rules alongside the chosen one so the register's comparative claim
(the W1 baseline double-counts; this rule conserves) is executable rather than
merely asserted.

**Every session here exists to kill a specific mutation.** The suite was built
by mutating the implementation and adding whatever fixture the survivors
required — three review rounds found nine mutations that changed behaviour while
the tests stayed green, each one a missing shape rather than a wrong assertion.
If you add a case to the rule, mutate it first and check something fails.
