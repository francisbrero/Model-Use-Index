# Guardrail — captured data and prompt content

**Enforcement: warn.** Fires on work touching transcripts, session records,
excerpts, fixtures, or anything under `phase0/`.

## The invariant

No prompt content leaves the machine, and none of it is ever committed
(`CLAUDE.md` invariant 6, PRD §13 Privacy, G4).

This repo is unusual: its *input* is real Claude Code transcripts containing the
operator's actual prompts, file contents, and shell commands. The normal
instinct — paste a sample record into a test, a docstring, an issue, or a PR
body — leaks real content here.

## Before you write it

- **Fixtures must be synthetic and obviously so.** Hand-write them. Don't copy a
  real record and edit the names — residual paths, branch names and command
  strings survive that process.
- **Excerpts keep verbs, not commands.** `pytest`, `git`, `npm` — never the full
  command line. Relative paths, never full paths.
- **Never log prompt text**, including in an error message or a `parse_degraded`
  diagnostic. Log the record's `uuid` and `cc_version` and look it up locally.
- **Telemetry env vars live in the shell profile**, outside this repo — a
  repo-committed telemetry header is a known exfiltration vector. OTLP binds to
  `127.0.0.1`.
- **This tool emits no telemetry about itself.**

## Before you commit

```bash
git diff --cached --stat | grep -nEi '\.jsonl|\.db|transcripts?/|delegations'
git diff --cached | grep -nEi 'sk-ant-|sk-proj-|Bearer |AUTH_SECRET|DATABASE_URL'
git diff --cached | grep -nE '/Users/[a-z]+/'
```

Any hit is a stop-and-fix. Check the PR body separately — it isn't in the diff.
