"""U1 — the Codex accounting rule, locked against a scrubbed fixture.

Codex rollout logs carry token counts, which is what U1 asked. The dangerous
part is *how* they carry them, and it is a different trap from invariant 10's:

- `total_token_usage` is **cumulative per session**. Summing it across records
  overstates by **26x** on this operator's real logs.
- `last_token_usage` is per-turn, but Codex emits **duplicate `token_count`
  events** — the same turn reported twice with `total` unchanged. Summing
  `last` overstates by **20%**.

The correct rule (`codex-final-total-v1`) is: take the FINAL
`total_token_usage` per session. Measured over 119 real sessions, that gives
136,500,627 input tokens where naive summing gives 3,570,607,085.

No Codex reader is built yet (second provider, out of M1's scope). This test
exists so that when one is, the rule is already executable rather than a
paragraph somebody has to find. Fixture is hand-written and obviously synthetic
(invariant 6).
"""

import json
import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "codex_session"


@pytest.fixture(scope="module")
def records():
    return [
        json.loads(line)
        for line in (FIXTURES / "codex_session.jsonl").read_text().splitlines()
        if line.strip()
    ]


@pytest.fixture(scope="module")
def expected():
    return json.loads((FIXTURES / "expected.json").read_text())


def token_events(records):
    """Every `token_count` event carrying usage. An event with `info: null`
    occurs in real logs and must not crash a reader (invariant 7)."""
    out = []
    for record in records:
        payload = record.get("payload") or {}
        if payload.get("type") != "token_count":
            continue
        info = payload.get("info") or {}
        if info.get("total_token_usage"):
            out.append(info)
    return out


def session_total(records):
    """`codex-final-total-v1` — the final cumulative snapshot, nothing summed."""
    events = token_events(records)
    return events[-1]["total_token_usage"] if events else None


def test_the_fixture_is_obviously_synthetic(records):
    """Invariant 6. A real rollout log carries the operator's prompts and
    paths; this must be visibly not one."""
    blob = json.dumps(records)
    assert "SYNTH-codex" in blob
    assert "/synthetic/repo" in blob
    assert "/Users/" not in blob


def test_codex_logs_carry_all_four_token_fields(records, expected):
    """U1's actual question. The four fields map onto the Anthropic ones the
    registry already prices separately, so this needs new registry rows rather
    than a new shape."""
    usage = session_total(records)
    for field in (
        "input_tokens",
        "cached_input_tokens",
        "cache_write_input_tokens",
        "output_tokens",
    ):
        assert field in usage
    assert usage == expected["correct_totals"]


def test_reasoning_tokens_are_present_and_have_no_anthropic_analogue(records):
    """Reported inside the turn. Whether it is additive to `output_tokens` or a
    subset must be checked against a rate card before pricing — getting it
    wrong is a per-turn error on the most expensive field."""
    assert "reasoning_output_tokens" in session_total(records)


def test_summing_total_token_usage_is_the_26x_error(records, expected):
    """The cumulative trap. Worse than invariant 10's 2x because it compounds
    with every turn in the session."""
    naive = sum(e["total_token_usage"]["input_tokens"] for e in token_events(records))
    assert naive == expected["wrong_if_summing_total"]["input_tokens"]
    assert naive > session_total(records)["input_tokens"]


def test_summing_last_token_usage_is_also_wrong(records, expected):
    """The subtler trap, and the one a careful reader would fall into: `last`
    IS per-turn, but duplicate events report the same turn twice."""
    naive = sum(e["last_token_usage"]["input_tokens"] for e in token_events(records))
    assert naive == expected["wrong_if_summing_last"]["input_tokens"]
    assert naive > session_total(records)["input_tokens"]


def test_the_fixture_contains_a_duplicate_event(records):
    """Without one, the fixture would not reproduce why summing `last` fails,
    and the rule would look like an arbitrary preference."""
    totals = [e["total_token_usage"]["input_tokens"] for e in token_events(records)]
    assert len(totals) > len(set(totals)), "a repeated cumulative total is required"


def test_an_event_with_no_usage_does_not_crash_the_reader(records):
    """`info: null` occurs in real logs."""
    nulls = [
        r
        for r in records
        if (r.get("payload") or {}).get("type") == "token_count"
        and not (r.get("payload") or {}).get("info")
    ]
    assert nulls, "the fixture must include one"
    assert session_total(records) is not None


def test_allowance_is_directly_readable_for_this_pool(records, expected):
    """U3's OpenAI half. `used_percent` for both windows is `allowance_pct`
    read rather than modelled — the PRD's primary measure, for free, for this
    pool. The Anthropic pool has no equivalent and must still be fitted, which
    is why the two pools cannot be rendered identically."""
    limits = [
        (r["payload"] or {}).get("rate_limits")
        for r in records
        if (r.get("payload") or {}).get("type") == "token_count"
    ]
    final = [rl for rl in limits if rl][-1]
    assert final["primary"]["used_percent"] == (
        expected["final_rate_limits"]["primary_used_percent"]
    )
    assert final["primary"]["window_minutes"] == 300
    assert final["secondary"]["window_minutes"] == 10080
    assert "resets_at" in final["primary"]


def test_codex_value_never_joins_the_anthropic_pool(records):
    """Invariant 4, stated where a future reader will be looking. Codex
    consumption belongs to the OpenAI ceiling and never contributes to an
    Anthropic total, however tempting one combined number looks."""
    usage = session_total(records)
    assert usage["input_tokens"] > 0
    # There is deliberately no assertion combining this with Anthropic figures:
    # the absence is the point, and this test documents it.
