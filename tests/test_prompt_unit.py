"""`prompt-unit-v1` — the boundary rule, and the 24x trap it avoids.

The obvious reading of "a user turn plus the work it triggered" is "cut at
every `user` record". That is wrong by 24x, and the reason is not visible from
the schema: Claude Code writes TOOL RESULTS BACK AS `user`-ROLE RECORDS, and
they are 92% of all `user` records (41,224 of 44,680 measured over Phoenix).

Cutting at every one of them yields ~44,000 units against W1's 1,823, which
would put the 43.4% score-0 target permanently out of reach — and since the
signal thresholds are fixed, the only way to "fix" it would be to retune them
until the headline reappeared. So this rule is tested at the boundary itself.
"""

from mui.normalize.work_unit import is_prompt_boundary


def user(content, **overrides):
    record = {"type": "user", "message": {"content": content}}
    record.update(overrides)
    return record


def test_a_plain_string_prompt_is_a_boundary():
    assert is_prompt_boundary(user("add a column to the report"))


def test_a_text_block_prompt_is_a_boundary():
    assert is_prompt_boundary(user([{"type": "text", "text": "do the thing"}]))


def test_an_image_prompt_is_a_boundary():
    assert is_prompt_boundary(user([{"type": "image", "source": {}}]))


def test_a_tool_result_is_NOT_a_boundary():
    """The single most important assertion in this module. 92% of `user`
    records are these."""
    assert not is_prompt_boundary(user([{"type": "tool_result", "content": "exit 0"}]))


def test_a_tool_result_alongside_text_is_still_not_a_boundary():
    """A mixed record is a tool result carrying commentary, not a new prompt.
    Treating it as a boundary would split a unit mid-work."""
    assert not is_prompt_boundary(
        user(
            [
                {"type": "text", "text": "here is the output"},
                {"type": "tool_result", "content": "exit 0"},
            ]
        )
    )


def test_meta_records_are_not_boundaries():
    """Harness chatter, not the operator asking for something."""
    assert not is_prompt_boundary(user("system notice", isMeta=True))


def test_sidechain_prompts_are_not_boundaries():
    """A subagent's prompt belongs to its parent unit — per-routine figures
    include their subagent cost by construction (U10, invariant 10 §6).
    Treating it as a boundary would attribute the parent's cost to the child.
    """
    assert not is_prompt_boundary(user("subagent task", isSidechain=True))


def test_assistant_records_are_not_boundaries():
    assert not is_prompt_boundary({"type": "assistant", "message": {"content": "sure"}})


def test_empty_and_whitespace_prompts_are_not_boundaries():
    assert not is_prompt_boundary(user(""))
    assert not is_prompt_boundary(user("   \n  "))


def test_an_unknown_content_shape_is_not_a_boundary():
    """Fail closed. Inventing a boundary from a shape we do not recognise would
    fragment units silently (invariant 7 — parse defensively)."""
    assert not is_prompt_boundary(user(None))
    assert not is_prompt_boundary(user({"unexpected": "dict"}))


def test_the_realistic_mix_yields_the_expected_boundary_count():
    """One prompt followed by a run of tool results is ONE unit, not five.

    This is the 24x bug in miniature: the naive rule would score 5 here.
    """
    stream = [
        user("fix the failing test"),
        user([{"type": "tool_result", "content": "FAILED"}]),
        user([{"type": "tool_result", "content": "FAILED"}]),
        user([{"type": "tool_result", "content": "ok"}]),
        user([{"type": "tool_result", "content": "ok"}]),
    ]
    assert sum(1 for r in stream if is_prompt_boundary(r)) == 1
