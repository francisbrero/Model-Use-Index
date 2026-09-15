"""W1's measured reference figures, loaded from local config — never committed.

`mui verify` checks the pipeline against figures hand-computed in W1 over the
operator's real transcript history. Those figures are measurements of one
person's private usage, so they live in the gitignored `config.toml` and this
repository ships **no default for any of them**.

That creates the obvious hazard, and it is the one thing this module exists to
prevent: a check with no reference must not quietly become a check that passes.
`Reference.load()` returns `None` when nothing is configured, and `verify.py`
turns that into a loud SKIP that still fails the exit code. A vacuous pass would
be worse than no gate at all, because it reads as a green tick.

Unlike the signal thresholds — which stay in code on purpose, see the NOTE in
`config.toml.example` — these are not knobs that change what the pipeline
computes. They are the answers it is measured against, which is why moving them
out of code is safe and moving a threshold out would not be.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


def _config_path() -> Path:
    """The live, gitignored config. Deliberately does NOT fall back to
    `config.toml.example` — the example carries no reference figures, and a
    fallback would only add a second way to get a silent empty result.

    Resolved relative to this file, which assumes the repo-root layout of an
    editable install. That holds for the single-operator scope this tool is
    scoped to (PRD §3 non-goals) and would need revisiting only if it were ever
    installed from a wheel — at which point the failure is a loud SKIP, not a
    wrong number.
    """
    return Path(__file__).resolve().parents[2] / "config.toml"


@dataclass(frozen=True)
class Reference:
    """W1's figures. Split by how `verify.py` uses them.

    ASSERTED — gate the exit code:
        `release_target` over `release_runs` runs, within `release_tolerance`.
        Pinned to a NAMED ROUTINE because corpus totals drift while a routine's
        total does not (U10).
        `prompt_unit_band` and `duplicate_ratio_band` are bands for the same
        reason.

    REPORTED — printed beside the live figure, never asserted, because the
    corpus grows while it is being measured:
        `frontier_unique`, `frontier_value`, `subset_share`,
        `remainder_share`, `score_zero_share`.
    """

    release_target: float
    release_runs: int
    release_tolerance: float
    prompt_unit_band: tuple[int, int]
    duplicate_ratio_band: tuple[float, float]

    frontier_unique: int | None = None
    frontier_value: float | None = None
    subset_share: float | None = None
    remainder_share: float | None = None
    score_zero_share: float | None = None

    @classmethod
    def load(cls, config_path: Path | None = None) -> Reference | None:
        """Return the configured reference, or `None` if unconfigured.

        `None` is the normal state for a fresh checkout and is not an error
        here — it becomes one in `verify.py`, where it is visible in the
        output rather than swallowed.

        A partially-filled `[reference]` section is a mistake worth surfacing,
        so a missing ASSERTED key raises rather than defaulting.
        """
        path = config_path if config_path is not None else _config_path()
        if not path.exists():
            return None
        section = tomllib.loads(path.read_text()).get("reference")
        if not section:
            return None

        try:
            band = section["prompt_unit_band"]
            ratio_band = section["duplicate_ratio_band"]
            return cls(
                release_target=float(section["release_target"]),
                release_runs=int(section["release_runs"]),
                release_tolerance=float(section.get("release_tolerance", 0.05)),
                prompt_unit_band=(int(band[0]), int(band[1])),
                duplicate_ratio_band=(float(ratio_band[0]), float(ratio_band[1])),
                frontier_unique=_opt_int(section.get("frontier_unique")),
                frontier_value=_opt_float(section.get("frontier_value")),
                subset_share=_opt_float(section.get("subset_share")),
                remainder_share=_opt_float(section.get("remainder_share")),
                score_zero_share=_opt_float(section.get("score_zero_share")),
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError(
                f"[reference] in {path.name} is incomplete or malformed: {exc}. "
                "Fill in every asserted key or remove the section entirely — a "
                "half-configured reference is how a check passes vacuously."
            ) from exc


def _opt_int(value: object) -> int | None:
    return None if value is None else int(value)  # type: ignore[arg-type]


def _opt_float(value: object) -> float | None:
    return None if value is None else float(value)  # type: ignore[arg-type]
