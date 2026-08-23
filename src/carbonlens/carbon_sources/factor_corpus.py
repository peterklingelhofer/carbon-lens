"""Loader for the versioned emission-factor corpus at ``data/emission-factors.json``.

The corpus is the single source of truth for lifecycle emission factors, shared
with carbon-aware-dispatcher so the two repositories cannot publish different
numbers for the same physical quantity under the same citation. This module owns
the file; the dispatcher vendors a copy.

Loading is strict and happens at import time. A factor record must either resolve
its ``citation`` against a citekey in ``docs/CITATIONS.csl.json``, or declare
itself an assumption (``citation: null`` plus an ``assumption`` string and
evidence tier E). Anything else raises, so a factor can never reach the API with
no stated basis at all.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

EvidenceTier = Literal["A", "B", "C", "D", "E"]

# data/ and docs/ sit next to src/, so walk up out of the installed package.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CORPUS_PATH = _REPO_ROOT / "data" / "emission-factors.json"
_CITATIONS_PATH = _REPO_ROOT / "docs" / "CITATIONS.csl.json"

_VALID_TIERS = {"A", "B", "C", "D", "E"}


class FactorCorpusError(RuntimeError):
    """The corpus is missing, malformed, or has a factor with no stated basis."""


@dataclass(frozen=True)
class EmissionFactor:
    """One fuel's lifecycle emission factor plus the provenance behind it."""

    key: str
    value: float | None
    fuel_class: str
    renewable: bool
    carbon_free: bool
    storage: bool
    citation: str | None
    source_row: str | None
    evidence_tier: EvidenceTier
    assumption: str | None
    deviation: dict[str, Any] | None

    @property
    def is_assumed(self) -> bool:
        """True when no source backs this factor and it must be flagged to callers."""
        return self.citation is None


@dataclass(frozen=True)
class FactorCorpus:
    """The parsed corpus: factors by key, plus the metadata identifying the version."""

    corpus_version: str
    updated: str
    unit: str
    basis: str
    factors: dict[str, EmissionFactor]

    def value(self, key: str, default_key: str = "other") -> float:
        """Emission factor for a fuel, falling back to the unknown-fuel bucket.

        Storage keys have no factor and must never be resolved through here;
        callers exclude them from the mix instead.
        """
        factor = self.factors.get(key) or self.factors[default_key]
        if factor.value is None:
            raise FactorCorpusError(
                f"{factor.key!r} is storage and has no emission factor; exclude it from the mix"
            )
        return factor.value


def _load_citekeys() -> set[str]:
    """Every citekey defined in the CSL-JSON corpus."""
    try:
        entries = json.loads(_CITATIONS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FactorCorpusError(f"citation corpus not found at {_CITATIONS_PATH}")
    except json.JSONDecodeError as exc:
        raise FactorCorpusError(f"citation corpus is not valid JSON: {exc}")
    return {entry["id"] for entry in entries if "id" in entry}


def _parse_factor(raw: dict[str, Any], citekeys: set[str]) -> EmissionFactor:
    """Validate one factor record and turn it into an EmissionFactor.

    Enforces the corpus contract: a stated basis (resolvable citekey or declared
    assumption), a valid tier, and a value unless the record is storage.
    """
    key = raw.get("key")
    if not key or not isinstance(key, str):
        raise FactorCorpusError(f"factor record has no string 'key': {raw!r}")

    tier = raw.get("evidence_tier")
    if tier not in _VALID_TIERS:
        raise FactorCorpusError(
            f"{key!r}: evidence_tier {tier!r} is not one of {sorted(_VALID_TIERS)}"
        )

    citation = raw.get("citation")
    assumption = raw.get("assumption")
    if citation is None:
        # No source. Only allowed as an explicitly declared tier-E assumption, so
        # an unsourced number can never pass silently as a cited one.
        if not assumption:
            raise FactorCorpusError(
                f"{key!r} has no citation and no 'assumption' explaining why. "
                "Every factor must state its basis; write the assumption down instead."
            )
        if tier != "E":
            raise FactorCorpusError(f"{key!r} is an assumption but claims evidence tier {tier!r}")
    elif citation not in citekeys:
        raise FactorCorpusError(
            f"{key!r} cites {citation!r}, which is not a citekey in {_CITATIONS_PATH.name}"
        )

    storage = bool(raw.get("storage", False))
    value = raw.get("value")
    if storage:
        if value is not None:
            raise FactorCorpusError(f"{key!r} is storage and must have a null value, got {value!r}")
    elif not isinstance(value, int | float):
        raise FactorCorpusError(f"{key!r} has a non-numeric value {value!r}")

    return EmissionFactor(
        key=key,
        value=float(value) if isinstance(value, int | float) else None,
        fuel_class=str(raw.get("class", "unknown")),
        renewable=bool(raw.get("renewable", False)),
        carbon_free=bool(raw.get("carbon_free", False)),
        storage=storage,
        citation=citation,
        source_row=raw.get("source_row"),
        evidence_tier=tier,
        assumption=assumption,
        deviation=raw.get("deviation"),
    )


@lru_cache(maxsize=1)
def load_corpus() -> FactorCorpus:
    """Parse and validate the factor corpus. Cached; raises on any contract breach."""
    try:
        doc = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FactorCorpusError(f"emission-factor corpus not found at {_CORPUS_PATH}")
    except json.JSONDecodeError as exc:
        raise FactorCorpusError(f"emission-factor corpus is not valid JSON: {exc}")

    citekeys = _load_citekeys()
    factors: dict[str, EmissionFactor] = {}
    for raw in doc.get("factors", []):
        factor = _parse_factor(raw, citekeys)
        if factor.key in factors:
            raise FactorCorpusError(f"duplicate factor key {factor.key!r}")
        factors[factor.key] = factor

    if "other" not in factors:
        raise FactorCorpusError("corpus must define an 'other' fallback factor")

    # `petroleum` is an alias of `oil`; a silent drift between them would mean the
    # same fuel scoring differently depending on which provider reported it.
    oil, petroleum = factors.get("oil"), factors.get("petroleum")
    if oil and petroleum and oil.value != petroleum.value:
        raise FactorCorpusError(
            f"'petroleum' ({petroleum.value}) and 'oil' ({oil.value}) are the same "
            "quantity and must carry the same value"
        )

    return FactorCorpus(
        corpus_version=str(doc.get("corpus_version", "unknown")),
        updated=str(doc.get("updated", "unknown")),
        unit=str(doc.get("unit", "gCO2eq/kWh")),
        basis=str(doc.get("basis", "lifecycle")),
        factors=factors,
    )
