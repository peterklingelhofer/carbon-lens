"""Serve the citation corpus over the wire.

Any number this API returns carries a `provenance` block naming citekeys. These
endpoints resolve them, so a consumer can trace a figure to its basis without
leaving the API. That is the point of the whole apparatus: provenance a caller
cannot follow is decoration.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from carbonlens.carbon_sources.factor_corpus import _CITATIONS_PATH, load_corpus

router = APIRouter()


class CitationSummary(BaseModel):
    """One corpus entry, flattened for the wire."""

    id: str
    title: str
    year: int | str | None = None
    authors: list[str] = Field(default_factory=list)
    doi: str | None = None
    url: str | None = None
    group: str
    verification: str = Field(
        description="How the bibliographic record was checked. primary-read means the "
        "document was retrieved and the relevant passage read; crossref-verified means "
        "the DOI resolves and the metadata matched; unverified means neither. This "
        "describes the CITATION, never the truth of the claim.",
    )
    access_level: str
    evidence_tier: str = Field(description="A (strongest) to E (assumed, no source)")
    backs_claims: list[str] = Field(
        default_factory=list, description="What this source is cited for in this codebase"
    )
    caveat: str | None = Field(
        default=None, description="Limits on how far this source can be relied on"
    )


class CitationList(BaseModel):
    total: int
    corpus_version: str = Field(description="Version of the emission-factor corpus in use")
    citations: list[CitationSummary]


def _year(entry: dict[str, Any]) -> int | str | None:
    try:
        return entry["issued"]["date-parts"][0][0]
    except (KeyError, IndexError, TypeError):
        return None


def _authors(entry: dict[str, Any]) -> list[str]:
    out = []
    for author in entry.get("author") or []:
        if author.get("literal"):
            out.append(author["literal"])
        else:
            out.append(", ".join(p for p in (author.get("family"), author.get("given")) if p))
    return out


def _summarize(entry: dict[str, Any]) -> CitationSummary:
    custom = entry.get("custom") or {}
    return CitationSummary(
        id=entry["id"],
        title=entry.get("title", ""),
        year=_year(entry),
        authors=_authors(entry),
        doi=entry.get("DOI"),
        url=entry.get("URL"),
        group=custom.get("group", "unknown"),
        verification=custom.get("verification", "unverified"),
        access_level=custom.get("accessLevel", "unknown"),
        evidence_tier=custom.get("evidenceTier", "E"),
        backs_claims=list(custom.get("backsClaims") or []),
        caveat=custom.get("caveat"),
    )


@lru_cache(maxsize=1)
def _corpus() -> dict[str, CitationSummary]:
    """The corpus keyed by citekey. Cached; the file is read-only at runtime."""
    entries = json.loads(_CITATIONS_PATH.read_text(encoding="utf-8"))
    return {entry["id"]: _summarize(entry) for entry in entries}


@router.get("/citations", response_model=CitationList, tags=["Provenance"])
async def list_citations(
    group: str | None = Query(
        default=None,
        description="Filter to one group: emission-factors, methodology, grid-data, "
        "compute-energy, standards",
    ),
    evidence_tier: str | None = Query(
        default=None, description="Filter to one evidence tier, A to E"
    ),
) -> CitationList:
    """The full citation corpus behind every number this API returns.

    Each `provenance.citations` entry on a carbon reading is a key into this list.
    """
    items = list(_corpus().values())
    if group:
        items = [c for c in items if c.group == group]
    if evidence_tier:
        items = [c for c in items if c.evidence_tier == evidence_tier.upper()]
    return CitationList(
        total=len(items),
        corpus_version=load_corpus().corpus_version,
        citations=sorted(items, key=lambda c: c.id),
    )


@router.get("/citations/{citation_id}", response_model=CitationSummary, tags=["Provenance"])
async def get_citation(citation_id: str) -> CitationSummary:
    """Resolve a single citekey from a reading's `provenance.citations`."""
    entry = _corpus().get(citation_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unknown citekey: {citation_id}")
    return entry
