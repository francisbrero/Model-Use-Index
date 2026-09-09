# Anchor-shape fixtures — U10

**Synthetic. Hand-written. Not scrubbed real data** (invariant 6, TD §11).

Session ids are `SYNTH-*`, paths are `/synthetic/repo`, message ids are
`msg_synth_*`. No real prompt text, file path, shell command or session id
appears here. Token counts are round numbers chosen to make the expected
attribution arithmetic checkable by hand.

`anchor_shapes.jsonl` encodes the five shapes U10 characterised, one session
each. `expected.json` gives the arc boundaries and per-routine Opus notional
list value that `normalize/work_unit.py` must reproduce under the U10 rule
(*anchor → next anchor of any skill, else session end*).

| Session | Shape | Why it is here |
|---|---|---|
| `SYNTH-single` | one anchor, work continues after the tag | the base case — the tag undercounts, the arc does not |
| `SYNTH-two-distinct` | two anchors, different skills | the boundary case the rule exists for |
| `SYNTH-two-same` | same skill invoked twice | re-invocation is a boundary, not a merge |
| `SYNTH-pre-anchor` | untagged work before the first anchor | must land in the unattributable remainder |
| `SYNTH-idle-gap` | a 6-day gap *inside* one arc | the case that kills an idle-time threshold |

The last row is the load-bearing one: a release routine waiting on CI produces
gaps of hours to days, so a gap is not evidence the arc ended.
