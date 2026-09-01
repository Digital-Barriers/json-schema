#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

from linkml.generators.jsonschemagen import JsonSchemaGenerator


ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    "AnalyticConfigurationDocument": (
        ROOT / "linkml/configuration.yaml",
        ROOT / "analytic-configuration.schema.json",
        "https://raw.githubusercontent.com/Digital-Barriers/json-schema/release/v2.0/analytic-configuration.schema.json",
    ),
    "ScenarioDocument": (
        ROOT / "linkml/configuration.yaml",
        ROOT / "scenario.schema.json",
        "https://raw.githubusercontent.com/Digital-Barriers/json-schema/release/v2.0/scenario.schema.json",
    ),
    "AnalyticEngineConfigurationDocument": (
        ROOT / "linkml/configuration.yaml",
        ROOT / "analytic-engine-configuration.schema.json",
        "https://raw.githubusercontent.com/Digital-Barriers/json-schema/release/v2.0/analytic-engine-configuration.schema.json",
    ),
    "EventDocument": (
        ROOT / "linkml/events.yaml",
        ROOT / "event.schema.json",
        "https://raw.githubusercontent.com/Digital-Barriers/json-schema/release/v2.0/event.schema.json",
    ),
}


def render(source: Path, top_class: str, schema_id: str) -> str:
    rendered = JsonSchemaGenerator(
        source,
        top_class=top_class,
        not_closed=False,
        include_null=False,
        include_range_class_descendants=True,
    ).serialize()
    document = json.loads(rendered)
    document["$id"] = schema_id
    document["title"] = top_class
    return json.dumps(document, indent=4, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Papillon JSON Schema contracts.")
    parser.add_argument("--check", action="store_true", help="Fail when checked-in schemas are stale.")
    args = parser.parse_args()

    stale = []
    for top_class, (source, target, schema_id) in TARGETS.items():
        generated = render(source, top_class, schema_id)
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
