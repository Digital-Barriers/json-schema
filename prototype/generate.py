#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

from linkml.generators.jsonschemagen import JsonSchemaGenerator


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "papillon-contract.yaml"
TARGETS = {
    "ParameterDocument": ROOT / "generated" / "parameter.schema.json",
    "EventDocument": ROOT / "generated" / "event.schema.json",
}


def render(top_class):
    rendered = JsonSchemaGenerator(
        SOURCE,
        top_class=top_class,
        not_closed=True,
        include_null=False,
        include_range_class_descendants=True,
    ).serialize()
    json.loads(rendered)
    return rendered.rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="Generate the LinkML prototype JSON Schemas.")
    parser.add_argument("--check", action="store_true", help="Fail when checked-in schemas are stale.")
    args = parser.parse_args()

    stale = []
    for top_class, target in TARGETS.items():
        generated = render(top_class)
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != generated:
                stale.append(target.relative_to(ROOT))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(generated, encoding="utf-8")

    if stale:
        print(f"Stale generated schemas: {', '.join(map(str, stale))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
