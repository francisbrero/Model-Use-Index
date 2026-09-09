#!/bin/sh
# PreToolUse hook (Write|Edit|NotebookEdit) -- catch cost-accounting code being
# written mid-session, when the prompt-level hook never fired.
#
# The UserPromptSubmit hook only sees the opening prompt. A session that starts
# "implement the normaliser" and reaches usage-summing forty turns later would
# miss the reminder entirely -- and that is exactly where this bug lands.
#
# CLAUDE.md invariant 1: sh only, no network, exits 0 unconditionally.

payload=$(cat 2>/dev/null) || exit 0

# Fire on the specific token fields, not on the word "cost" -- this hook sees
# every file write, so a loose pattern would fire constantly and be tuned out.
printf '%s' "$payload" | grep -qE 'cache_read_input_tokens|cache_creation_input_tokens|output_tokens|input_tokens|message\.usage|allowance_pct|notional' || exit 0

cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "This edit touches token-usage fields. Check against `/token-accounting` (.claude/skills/token-accounting/SKILL.md): are records deduplicated by (message.id, requestId) with MAX per field before summing? Claude Code writes one record per content block, each repeating the same usage object -- naive summing overstates cost by ~91%. Are all four token fields priced separately? Is dedup in normalize/ rather than collect/ (invariant 2)? Is every dollar figure labelled 'notional list value'?"
  }
}
JSON
exit 0
