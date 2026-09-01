#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

import generate


ROOT = Path(__file__).resolve().parent
PAPILLON_EDGE_ROOT = Path(
    os.environ.get("PAPILLON_EDGE_ROOT", ROOT.parents[1] / "papillon-edge")
).resolve()


def load_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def make_validator(path):
    schema = load_json(path)
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    return schema, validator_class(schema, format_checker=FormatChecker())


def require_valid(validator, document, label):
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))
    if errors:
        raise AssertionError(f"{label} should be valid: {errors[0].message}")
    print(f"PASS valid:   {label}")


def require_invalid(validator, document, label):
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))
    if not errors:
        raise AssertionError(f"{label} should be invalid")
    print(f"PASS invalid: {label}")


def find_parameter(path, parameter_type):
    document = load_json(path)
    return next(parameter for parameter in document["parameters"] if parameter["type"] == parameter_type)


def check_generated_files():
    for top_class, target in generate.TARGETS.items():
        expected = generate.render(top_class)
        if target.read_text(encoding="utf-8") != expected:
            raise AssertionError(f"{target.relative_to(ROOT)} is stale")


def check_generated_structure(parameter_schema, event_schema):
    parameter_defs = parameter_schema["$defs"]
    assert parameter_defs["PParameterRangeInt"]["properties"]["type"]["const"] == "PParameterRangeInt"
    assert parameter_defs["PParameterRangeInt"]["properties"]["value"]["type"] == "integer"
    assert parameter_defs["PParameterRangeFloat"]["properties"]["type"]["const"] == "PParameterRangeFloat"
    assert parameter_defs["PParameterRangeFloat"]["properties"]["value"]["type"] == "number"
    assert parameter_defs["PParameterRangeInt"]["additionalProperties"] is False
    assert parameter_defs["PParameterRangeFloat"]["additionalProperties"] is False

    event_defs = event_schema["$defs"]
    assert event_defs["AlarmStartEvent"]["properties"]["type"]["const"] == "alarmStart"
    assert event_defs["AlarmStartEvent"]["properties"]["eventPayload"]["$ref"].endswith("AlarmStartPayload")
    assert event_defs["AlarmEndEvent"]["properties"]["type"]["const"] == "alarmEnd"
    assert event_defs["AlarmEndEvent"]["properties"]["eventPayload"]["$ref"].endswith("AlarmEndPayload")
    assert event_defs["AlarmStartPayload"]["additionalProperties"] is False
    assert event_defs["AlarmEndPayload"]["additionalProperties"] is False


def main():
    check_generated_files()
    parameter_schema, parameter_validator = make_validator(ROOT / "generated" / "parameter.schema.json")
    event_schema, event_validator = make_validator(ROOT / "generated" / "event.schema.json")
    check_generated_structure(parameter_schema, event_schema)

    magnetite = PAPILLON_EDGE_ROOT / "Data" / "ReleaseModels" / "Analytics" / "Engines" / "magnetite" / "beta"
    require_valid(
        parameter_validator,
        find_parameter(magnetite / "safezone_2d.json", "PParameterRangeInt"),
        "Magnetite PParameterRangeInt",
    )
    require_valid(
        parameter_validator,
        find_parameter(magnetite / "faceRecognition.json", "PParameterRangeFloat"),
        "Magnetite PParameterRangeFloat",
    )

    event_fixtures = PAPILLON_EDGE_ROOT / "Data" / "Unittest" / "SchemaContracts" / "events"
    require_valid(event_validator, load_json(event_fixtures / "alarmStart.json"), "alarmStart event")
    require_valid(event_validator, load_json(event_fixtures / "alarmEnd.json"), "alarmEnd event")

    invalid_dir = ROOT / "fixtures" / "invalid"
    for path in sorted(invalid_dir.glob("parameter-*.json")):
        require_invalid(parameter_validator, load_json(path), path.name)
    for path in sorted(invalid_dir.glob("event-*.json")):
        require_invalid(event_validator, load_json(path), path.name)

    print("LinkML prototype checkpoint passed: 4 valid and 6 invalid cases behaved as expected.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, ValueError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
