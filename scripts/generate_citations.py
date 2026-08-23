"""Turn docs/CITATIONS.csl.json into a type-checked citekey set and a readable bibliography.

Two outputs from one source of truth:

  src/carbonlens/citations_generated.py   a `CitationId` Literal of every valid
                                           citekey. Code that attaches a citekey to
                                           a constant is annotated with it, so an
                                           unknown key becomes a *type error* rather
                                           than a string that silently means nothing.
                                           This project gates on pyright, which is
                                           already wired into CI and pre-commit, so
                                           that is where the error surfaces. (The
                                           handoff called for mypy; pyright is the
                                           checker this repo actually runs, and a
                                           Literal fails identically under it. Adding
                                           a second type checker for one module would
                                           have been the worse trade.)

  docs/CITATIONS.md                        the human rendering, regenerated whole so
                                           the prose and the corpus cannot drift.

Duplicate citekeys, malformed citekeys, entries in an unknown group, and entries
missing a required `custom` field all fail the run.

Usage:
    uv run python scripts/generate_citations.py
    uv run python scripts/generate_citations.py --check   # CI: fail if stale
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "CITATIONS.csl.json"
TYPES = ROOT / "src" / "carbonlens" / "citations_generated.py"
MARKDOWN = ROOT / "docs" / "CITATIONS.md"

CITEKEY = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Section order in the rendered bibliography.
GROUPS = [
    ("emission-factors", "Emission factors"),
    ("methodology", "Methodology"),
    ("grid-data", "Grid data sources"),
    ("compute-energy", "Compute energy"),
    ("standards", "Standards & policy"),
]

VERIFICATION_LABEL = {
    "crossref-verified": "Crossref-verified",
    "datacite-verified": "DataCite-verified",
    "url-verified": "URL-verified",
    "primary-read": "PRIMARY TEXT READ",
    "unverified": "UNVERIFIED",
}

PREAMBLE = """# Citation corpus

{summary} Machine-readable companion: [`CITATIONS.csl.json`](./CITATIONS.csl.json) (CSL-JSON).

**This file is generated.** Edit `CITATIONS.csl.json` and run
`uv run python scripts/generate_citations.py`. CI fails if the two drift apart.

Verification pass completed 2026-08-23 against the Crossref REST API and direct fetches of
publisher, standards-body, grid-operator and government URLs.

## How to read this

### Verification status

This says how the *bibliographic record* was checked. It says nothing about whether the finding is true.

| Status | Meaning |
|---|---|
| `primary-read` | The document itself was retrieved and the passage this project relies on was read and quoted. The strongest status here. |
| `crossref-verified` | The DOI resolves in Crossref and the returned title, authors, year, container, volume and pages were compared against what this corpus claims. Any discrepancy is written into the caveat. |
| `url-verified` | No DOI, or no need of one. An authoritative URL (publisher, standards body, grid operator, government) was fetched on 2026-08-23 and the document identity confirmed from the response itself. |
| `unverified` | Neither a resolvable DOI nor a successfully fetched authoritative URL. Usually because the host blocks automated clients. The bibliographic details may be wrong, and the caveat says so. |

A `crossref-verified` record can still carry a loud caveat. **Verification confirms the *citation*, not
the *claim*.** Several entries here are Crossref-verified but were paywalled to full-text fetch, meaning
this project confirmed the paper exists and is what it says it is, and never read its numbers. Where a
number was actually read out of a document, the status is `primary-read` and the caveat quotes it.

### Access level

`open-access` | `paywalled` | `public-domain` (government, national-lab or intergovernmental output) |
`standard-purchase` (must be bought from a standards body).

### Evidence tier

The tier describes what the source licenses this product to *do* with the number, not how good the
source is in the abstract. A first-rate weather API is tier E for a carbon claim, because nothing in it
licenses a carbon claim.

| Tier | Definition | Product treatment |
|---|---|---|
| A | A grid operator's or standards body's own published methodology | May drive a headline number |
| B | Peer-reviewed method, independently replicated | May drive a headline number |
| C | Peer-reviewed but single-study, or a method published without validation | Renders as estimated, never as measured |
| D | Vendor white paper or self-reported figure with a stated method | Labelled, advisory only |
| E | Assumed, folk knowledge, or no source found | Must be visibly flagged in the API response |

The API surfaces this: every carbon-intensity response carries a `provenance` block naming the
citekeys behind the number and the lowest evidence tier among them, and `GET /api/v1/citations`
serves this corpus over the wire.

### Counts

{counts}

---
"""


def load() -> list[dict]:
    entries = json.loads(SOURCE.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise SystemExit("CITATIONS.csl.json must be a JSON array")
    return entries


def validate(entries: list[dict]) -> list[str]:
    """Reject duplicates, malformed keys, unknown groups and missing custom fields."""
    ids = [entry.get("id", "") for entry in entries]

    duplicates = sorted({key for key, n in Counter(ids).items() if n > 1})
    if duplicates:
        raise SystemExit(f"duplicate citekeys: {', '.join(duplicates)}")

    malformed = sorted(key for key in ids if not CITEKEY.match(key))
    if malformed:
        raise SystemExit(f"malformed citekeys: {', '.join(malformed)}")

    known_groups = {key for key, _ in GROUPS}
    problems: list[str] = []
    for entry in entries:
        custom = entry.get("custom") or {}
        if custom.get("group") not in known_groups:
            problems.append(f"{entry['id']}: unknown group {custom.get('group')!r}")
        if custom.get("verification") not in VERIFICATION_LABEL:
            problems.append(f"{entry['id']}: unknown verification {custom.get('verification')!r}")
        if custom.get("evidenceTier") not in {"A", "B", "C", "D", "E"}:
            problems.append(
                f"{entry['id']}: evidenceTier {custom.get('evidenceTier')!r} is not A-E"
            )
        if not custom.get("backsClaims"):
            problems.append(f"{entry['id']}: backsClaims is empty; every entry must back a claim")
        if not entry.get("DOI") and not entry.get("URL"):
            problems.append(f"{entry['id']}: has neither a DOI nor a URL")
    if problems:
        raise SystemExit("corpus problems:\n  " + "\n  ".join(problems))

    return sorted(ids)


def write_types(ids: list[str]) -> None:
    body = [
        '"""GENERATED by scripts/generate_citations.py from docs/CITATIONS.csl.json.',
        "",
        "Do not edit by hand. Run `uv run python scripts/generate_citations.py` after",
        "changing the CSL-JSON. Annotating a citekey with CitationId makes an unknown",
        "key a pyright error rather than a string that silently means nothing.",
        '"""',
        "",
        "from typing import Literal",
        "",
        "CitationId = Literal[",
        *(f'    "{key}",' for key in ids),
        "]",
        "",
        "CITATION_IDS: tuple[CitationId, ...] = (",
        *(f'    "{key}",' for key in ids),
        ")",
        "",
    ]
    TYPES.write_text("\n".join(body), encoding="utf-8")


def _names(authors: list[dict] | None) -> str | None:
    if not authors:
        return None
    return "; ".join(
        author["literal"]
        if author.get("literal")
        else ", ".join(p for p in (author.get("family"), author.get("given")) if p)
        for author in authors
    )


def _year(issued: dict | None) -> object:
    try:
        return (issued or {})["date-parts"][0][0]
    except (KeyError, IndexError, TypeError):
        return "n.d."


def _reference(entry: dict) -> str:
    parts = []
    who = _names(entry.get("author"))
    if who:
        parts.append(f"{who}.")
    parts.append(f"({_year(entry.get('issued'))}).")
    parts.append(f"*{entry['title']}*.")
    venue = entry.get("container-title") or entry.get("publisher")
    where = " ".join(p for p in (venue, entry.get("number")) if p)
    if where:
        parts.append(where.strip())
    locus = ": ".join(p for p in (entry.get("volume"), entry.get("page")) if p)
    if locus:
        parts.append(locus)
    return " ".join(parts).replace("  ", " ").replace(" .", ".")


def _render(entry: dict) -> str:
    custom = entry.get("custom") or {}
    lines = [f"#### `{entry['id']}`", "", _reference(entry), ""]
    if entry.get("DOI"):
        lines.append(f"- DOI: [{entry['DOI']}](https://doi.org/{entry['DOI']})")
    elif entry.get("URL"):
        lines.append(f"- URL: <{entry['URL']}>")
    label = VERIFICATION_LABEL.get(custom.get("verification"), custom.get("verification"))
    tier = custom.get("evidenceTier")
    lines.append(
        f"- Verification: {label} | Access: {custom.get('accessLevel')} | evidence tier **{tier}**"
    )
    lines.append("- Backs:")
    lines.extend(f"  - {claim}" for claim in custom.get("backsClaims", []))
    if custom.get("caveat"):
        lines.append(f"- **Caveat:** {custom['caveat']}")
    lines.append("")
    return "\n".join(lines)


def _table(heading: str, counted: dict, total: int | None = None) -> str:
    rows = [f"| {heading} | n |", "|---|---|"]
    rows.extend(f"| `{key}` | {value} |" for key, value in counted.items())
    if total is not None:
        rows.append(f"| **total** | **{total}** |")
    return "\n".join(rows)


def _tally(entries: list[dict], field: str) -> dict:
    return dict(sorted(Counter((e.get("custom") or {}).get(field) for e in entries).items()))


def write_markdown(entries: list[dict]) -> None:
    verification = _tally(entries, "verification")
    counts = "\n\n".join(
        [
            _table("Verification", verification, total=len(entries)),
            _table("Access level", _tally(entries, "accessLevel")),
            _table("Evidence tier", _tally(entries, "evidenceTier")),
            _table("Group", _tally(entries, "group")),
        ]
    )
    summary = (
        f"{len(entries)} sources ("
        + ", ".join(f"{n} {name}" for name, n in verification.items())
        + ")."
    )

    body = []
    for key, heading in GROUPS:
        group = sorted(
            (e for e in entries if (e.get("custom") or {}).get("group") == key),
            key=lambda e: e["id"],
        )
        body.append(
            "\n".join(
                [f"## {heading}", "", f"{len(group)} sources.", ""] + [_render(e) for e in group]
            )
        )

    rendered = PREAMBLE.format(summary=summary, counts=counts) + "\n" + "\n".join(body)
    MARKDOWN.write_text(re.sub(r"\n{3,}", "\n\n", rendered).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate citekey types and the bibliography")
    parser.add_argument(
        "--check", action="store_true", help="fail if the generated files are not up to date"
    )
    args = parser.parse_args(argv)

    entries = load()
    ids = validate(entries)

    if args.check:
        before = {p: p.read_text(encoding="utf-8") for p in (TYPES, MARKDOWN) if p.exists()}
        write_types(ids)
        write_markdown(entries)
        stale = [p for p, text in before.items() if p.read_text(encoding="utf-8") != text]
        if stale or len(before) < 2:
            names = ", ".join(str(p.relative_to(ROOT)) for p in stale) or "generated files"
            print(
                f"{names} out of date; run: uv run python scripts/generate_citations.py",
                file=sys.stderr,
            )
            return 1
        print(f"{len(ids)} citekeys, generated files up to date")
        return 0

    write_types(ids)
    write_markdown(entries)
    print(
        f"wrote {len(ids)} citekeys to {TYPES.relative_to(ROOT)} and {MARKDOWN.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
