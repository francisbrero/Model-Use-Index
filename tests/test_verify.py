"""`mui verify` must never pass vacuously.

The W1 reference figures are one operator's private measurements, so they moved
out of code into a gitignored `config.toml` that this repository ships no
default for (issue #25, the open-sourcing pass). That created exactly one
hazard worth a test: a gate with nothing to compare against could quietly
report green.

These tests pin the opposite behaviour. They are cheap, and they defend the
only thing that makes `mui verify` worth running.
"""

import pytest

from mui import db
from mui.reference import Reference
from mui.verify import run_checks


@pytest.fixture
def conn():
    """An empty but migrated store. Empty is the point: even with no data, the
    unconfigured run must fail rather than find nothing and shrug."""
    connection = db.connect(":memory:")
    db.migrate(connection)
    yield connection
    connection.close()


def _run(connection, **kwargs) -> tuple[int, list[str]]:
    lines: list[str] = []
    failures = run_checks(connection, echo=lines.append, **kwargs)
    return failures, lines


def test_no_reference_fails_rather_than_passing(conn):
    """The whole point. No `[reference]` configured -> non-zero, so the CLI
    exits 1 instead of printing 'all asserted checks passed'."""
    failures, lines = _run(conn, repo_filter="Demo", reference=None)
    assert failures > 0, "an unconfigured verify must FAIL, never pass vacuously"
    assert any("SKIP" in line for line in lines)


def test_no_reference_says_why(conn):
    """A skip an operator cannot explain is nearly as bad as a silent pass."""
    _, lines = _run(conn, repo_filter="Demo", reference=None)
    output = "\n".join(lines)
    assert "[reference]" in output and "config.toml.example" in output


def test_no_repo_skips_the_asserted_subset_check(conn):
    """`--repo` has no default now. The repo-scoped ASSERTED check must skip
    and count as a failure — falling back to matching every repo would answer
    a different question, and reporting it (rather than skipping) would not
    gate the exit code."""
    reference = Reference(
        release_target=100.0,
        release_runs=10,
        release_tolerance=0.05,
        prompt_unit_band=(1, 2),
        duplicate_ratio_band=(0.45, 0.52),
    )
    failures, lines = _run(conn, repo_filter=None, reference=reference)
    assert failures > 0
    assert any("prompt units" in line and "SKIP" in line for line in lines)


def test_no_repo_never_matches_the_literal_string_none(conn):
    """A `%None%` LIKE match reads zero rows and prints a confident zero."""
    _, lines = _run(conn, repo_filter=None, reference=None)
    output = "\n".join(lines)
    assert "None share" not in output
    assert "(None)" not in output


POPULATED = Reference(
    release_target=0.0,
    release_runs=0,
    release_tolerance=0.05,
    prompt_unit_band=(0, 0),
    duplicate_ratio_band=(0.0, 1.0),
    frontier_unique=37_781,
    frontier_value=23_059.0,
    subset_share=73.4,
    remainder_share=7.4,
    score_zero_share=43.4,
)


def test_reported_rows_never_gate_the_exit_code(conn):
    """A reported row is as-of-a-moment by design and must stay out of the
    failure count, or the corpus growing would fail the gate daily."""
    _, lines = _run(conn, repo_filter="Demo", reference=POPULATED)
    assert any("reported" in line for line in lines)


def test_a_reference_dollar_figure_announces_itself_as_one(conn):
    """Invariant 5. The expected column mixes counts, dollars and percentages,
    so a bare `23,059` beside an actual of `$0` reads as a count. The footer
    disclaims "all dollar figures are notional list value" — which does not
    reach a number that does not look like a dollar figure."""
    _, lines = _run(conn, repo_filter="Demo", reference=POPULATED)
    output = "\n".join(lines)
    assert "$23,059 (W1)" in output, "the currency marker must survive formatting"


def test_a_reference_percentage_announces_itself_as_one(conn):
    """`73.4` against an actual of `0.0%` invites reading the reference as an
    absolute."""
    _, lines = _run(conn, repo_filter="Demo", reference=POPULATED)
    output = "\n".join(lines)
    assert "73.4% (W1)" in output
    assert "7.4% (W1)" in output


def test_a_reference_count_carries_no_spurious_unit(conn):
    """The unit is per-row, not blanket — a response count is neither dollars
    nor a percentage."""
    _, lines = _run(conn, repo_filter="Demo", reference=POPULATED)
    output = "\n".join(lines)
    assert "37,781 (W1)" in output
    assert "$37,781" not in output and "37,781%" not in output


def test_a_half_filled_reference_section_raises(tmp_path):
    """A partially-filled section is a mistake worth surfacing loudly. Silently
    defaulting the missing half would reintroduce the vacuous pass."""
    config = tmp_path / "config.toml"
    config.write_text("[reference]\nrelease_runs = 10\n")
    with pytest.raises(ValueError, match="incomplete or malformed"):
        Reference.load(config)


def test_an_absent_config_is_not_an_error(tmp_path):
    """A fresh checkout has no `config.toml`. That is the normal state, and it
    becomes a failure in `verify.py` where it is visible — not an exception
    here, where it would be a crash."""
    assert Reference.load(tmp_path / "nope.toml") is None


def test_an_absent_reference_section_is_not_an_error(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[paths]\nstore = "~/x.db"\n')
    assert Reference.load(config) is None


def test_the_shipped_example_configures_no_reference():
    """`config.toml.example` must ship the section commented out. If it ever
    carries live values, this repository is publishing the operator's figures
    and every fresh checkout silently 'passes' against someone else's data."""
    from pathlib import Path

    example = Path(__file__).resolve().parents[1] / "config.toml.example"
    assert Reference.load(example) is None
