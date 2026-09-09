Create a pull request for the current branch.

Steps:

1. Read `.github/pull_request_template.md` if it exists.
2. Run `git log master..HEAD --oneline` to get commit history.
3. Run `git diff master..HEAD --stat` to get the changed files summary.
4. Fill in each section of the PR template using the git context.
5. Create the PR with `gh pr create --title "..." --body "..."`.

IMPORTANT: `gh pr create --body` overrides GitHub's template auto-fill.
You MUST read and reproduce the template manually in the `--body` argument.

## Repo-specific checks

### 1. Captured data must never land in a commit

This project's working data is real Claude Code transcripts, session records and
shell commands (CLAUDE.md invariant 6). Before creating the PR, verify the diff
**and the PR body** are free of captured content:

```bash
# Session/transcript records, DB files, real prompt text
git diff master..HEAD --stat | grep -nEi '\.jsonl|\.db|store\.db|transcripts?/|delegations'

# Credential and identifier shapes
git diff master..HEAD | grep -nEi 'sk-ant-|sk-proj-|AUTH_SECRET|DATABASE_URL|Bearer |arn:aws|[0-9]{12}'

# Absolute paths that leak machine/user layout
git diff master..HEAD | grep -nE '/Users/[a-z]+/'
```

Any hit is a stop-and-fix, not a judgement call. Fixtures are allowed only if
hand-scrubbed and obviously synthetic.

Check the PR body separately — it is not part of the diff, and pasting a sample
record into a PR description is the easiest way to leak one.

### 2. Invariant check

If the diff touches capture, normalisation or the verdict engine, confirm in the
PR body that these still hold (CLAUDE.md Project Invariants):

- Hooks `exit 0` unconditionally and stay under 50 ms
- `raw_event` is still append-only; no enrichment writes over capture
- Exactly one authoritative consumption source per provider
- No cross-pool summing of allowance
- Any dollar figure is labelled *notional list value*

### 3. Lint

```bash
ruff check . && ruff format --check .        # once there is Python
npx --yes markdownlint-cli2 <changed .md files>
```

Pre-existing warnings are expected. Fix what you introduced; don't reflow whole
documents.
