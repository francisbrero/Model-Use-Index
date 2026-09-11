"""Model tier resolution and notional list value.

Every figure this module produces is NOTIONAL LIST VALUE (invariant 5). We are
on seat subscriptions, not metered billing, so none of it is money anyone was
billed. It exists to rank work. The primary measure — share of a pool's period
allowance — is deliberately not computed by this slice (U3/U3a deferred).

Rates come from the versioned `model_registry` table, never from constants in
an analysis (token-accounting §2), so a rate correction re-values history
instead of corrupting it.
"""

from __future__ import annotations

import fnmatch
import sqlite3
from dataclasses import dataclass

# The four fields, in a fixed order. All four are priced separately: cache
# traffic is ~93% of Opus notional value here (57.9% read, 34.8% write) against
# 7.2% output, and pricing cache_read at the input rate is a 10x error on the
# largest line item.
USAGE_FIELDS = ("input", "output", "cache_write", "cache_read")


class UnknownModelError(LookupError):
    """Raised when a model matches no registry pattern.

    Deliberately loud. A silent tier default would corrupt every `tier_delta`
    in `verdict`, and the corruption would look like a finding rather than a
    bug (PRD §6.3).
    """


@dataclass(frozen=True)
class Rate:
    version: str
    provider: str
    pattern: str
    tier: str
    allowance_pool: str
    usd_in: float
    usd_out: float
    usd_cache_write: float
    usd_cache_read: float


class Registry:
    """The versioned rate registry, loaded once per run."""

    def __init__(self, rates: list[Rate], version: str):
        # Longest pattern first, so `claude-haiku-4-5*` wins over
        # `claude-haiku-4*` and a version-pinned id resolves the same way as its
        # unpinned form.
        self._rates = sorted(rates, key=lambda r: len(r.pattern), reverse=True)
        self.version = version

    @classmethod
    def load(cls, conn: sqlite3.Connection, version: str | None = None) -> Registry:
        if version is None:
            row = conn.execute("SELECT MAX(version) FROM model_registry").fetchone()
            version = row[0]
            if version is None:
                raise UnknownModelError("model_registry is empty — run migrations")
        rows = conn.execute(
            "SELECT * FROM model_registry WHERE version = ?", (version,)
        ).fetchall()
        return cls(
            [
                Rate(
                    r["version"],
                    r["provider"],
                    r["model_pattern"],
                    r["tier"],
                    r["allowance_pool"],
                    r["usd_per_mtok_in"],
                    r["usd_per_mtok_out"],
                    r["usd_per_mtok_cache_write"],
                    r["usd_per_mtok_cache_read"],
                )
                for r in rows
            ],
            version,
        )

    def resolve(self, model: str) -> Rate:
        for rate in self._rates:
            if fnmatch.fnmatchcase(model, rate.pattern):
                return rate
        raise UnknownModelError(
            f"no registry pattern matches model {model!r} "
            f"(registry version {self.version}). Add it rather than defaulting: "
            "a silent tier default corrupts every tier_delta."
        )

    def notional_list_value_usd(self, model: str, usage: dict[str, int]) -> float:
        """USD notional list value for one API response. NOT money billed."""
        rate = self.resolve(model)
        return (
            usage.get("input", 0) * rate.usd_in
            + usage.get("output", 0) * rate.usd_out
            + usage.get("cache_write", 0) * rate.usd_cache_write
            + usage.get("cache_read", 0) * rate.usd_cache_read
        ) / 1e6
