"""Export the FastAPI OpenAPI schema to a file.

Keeps a checked-in ``openapi.json`` in sync with the live API so clients can be
generated from it and CI can flag drift (a route changed but the spec wasn't
regenerated). Deterministic output (sorted keys) so the diff is meaningful.

Usage:
    uv run python scripts/export_openapi.py --out openapi.json
"""

import argparse
import json

from carbon_mesh.main import app


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the OpenAPI schema")
    parser.add_argument("--out", default="openapi.json", help="Output path")
    args = parser.parse_args()

    schema = app.openapi()
    with open(args.out, "w") as f:
        json.dump(schema, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"Wrote {args.out}: {len(schema.get('paths', {}))} paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
