#!/bin/sh
# UserPromptSubmit hook -- surface /token-accounting when a prompt is about
# cost, tokens or spend.
#
# Why: the naive reading of Claude Code transcripts overstates cost by ~91%
# (CLAUDE.md invariant 10). The mistake is invisible in the output, so the
# reminder must arrive before the query is written, not at review time.
#
# Same rules as the spool hook (CLAUDE.md invariant 1): sh not Python, no
# network, no lock, exits 0 unconditionally, never blocks a turn.

payload=$(cat 2>/dev/null) || exit 0

# Match the whole stdin payload rather than a specific field: the documented
# UserPromptSubmit stdin contract does not guarantee a `prompt` key, and a
# false negative here silently disables the guardrail. Over-matching costs a
# few tokens; under-matching costs a wrong published number.
printf '%s' "$payload" | grep -qiE '\$[0-9]|cost|spend|spent|token|usage|pricing|price|allowance|headroom|notional|burn.rate|ccusage|how much' || exit 0

cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "COST/TOKEN ACCOUNTING DETECTED. Load the `/token-accounting` skill (.claude/skills/token-accounting/SKILL.md) BEFORE writing any query, script or figure. The naive approach is wrong by ~2x. Non-negotiable: (1) deduplicate by (message.id, requestId) taking MAX per field -- Claude Code writes one JSONL record per content block and each repeats the same usage object, so naive summing overstates by ~91%; (2) price all four token fields separately -- cache traffic is ~93% of Opus value, and cache_read is 0.1x input so pricing it as input is a 10x error; (3) never sum across allowance pools; (4) label every dollar figure 'notional list value'; (5) attributionSkill is an anchor, not a cost attributor. A wrong number is worse than no number because it will be believed."
  }
}
JSON
exit 0
