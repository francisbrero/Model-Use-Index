# Guardrail — never break the thing being observed

**Enforcement: warn.** Fires on hook code, file-watcher/tailer code, and
anything that runs during an interactive Claude Code turn.

## The invariant

Nothing in this system may ever break or slow Claude Code (`CLAUDE.md`
invariant 1, PRD §13 Failure isolation, G5).

The p95 added latency target is **0 ms**, and it's a hard constraint rather than
an aspiration. It's the reason classification is a nightly batch job.

## Rules for hook code

**A hook must not be Python** (TD §4). Interpreter startup is 50–100 ms — a
measurable tax on every tool call. The hook is one line of `sh` that spools its
stdin payload and exits, at roughly 1 ms:

```sh
#!/bin/sh
# ~/.model-use-index/hooks/spool.sh — registered for every hook we consume
exec cat > "$HOME/.model-use-index/spool/$(date +%s)-$$-$PPID.json"
```

`mui-collect` drains the spool directory and deletes what it ingests. All the
logic lives there, where it can fail safely.

- **One file per invocation, into a spool directory — never a shared append-only
  file.** Appends under `PIPE_BUF` to an `O_APPEND` file are atomic, but hook
  payloads can exceed it and interleaved writes corrupt records *invisibly*,
  which is the worst failure mode available. A file per invocation costs nothing
  and cannot interleave.
- **`exit 0` unconditionally.** Every path, including the error path. A non-zero
  exit can wedge a turn.
- **No interpreter, no network, no model call, no lock, no DB write.** If you're
  tempted to add any of these, it belongs in the collector, not the hook.
- **Non-blocking.** Never `sleep`, never retry, never wait on a subprocess whose
  runtime you don't control.
- A lost hook record is recoverable from the transcript later. A hung session is
  not. When in doubt, drop the record.

## Rules for the tailer / watcher

- Never hold a lock on a transcript Claude Code may be writing. Read-only, and
  tolerate a partially-written trailing line.
- Falling behind is fine; crashing is fine (files stay on disk and backfill).
  Corrupting or truncating a transcript is not.

## The risk asymmetry that settles design arguments

Every source must fail toward *"the tool is degraded"*, never toward *"the
workday stopped"* (§5.1, §5.2). If a proposed design puts the failure on the
Claude Code side — a proxy, an inline classifier, a blocking hook — that's the
argument against it, and it usually outweighs whatever the design was buying.
