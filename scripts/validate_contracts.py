#!/usr/bin/env python3

import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft201909Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
PAPILLON_EDGE = Path(os.environ.get("PAPILLON_EDGE_ROOT", ROOT.parent / "papillon-edge"))
CORPUS = PAPILLON_EDGE / "Data/Unittest/SchemaContracts"
MAGNETITE = PAPILLON_EDGE / "Data/ReleaseModels/Analytics/Engines/magnetite"


class ContractError(ValueError):
    pass


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def validator(name: str) -> Draft201909Validator:
    schema = load(ROOT / f"{name}.schema.json")
    Draft201909Validator.check_schema(schema)
    return Draft201909Validator(schema, format_checker=FormatChecker())


def validate_json(document: dict[str, Any], check: Draft201909Validator, label: str) -> None:
    errors = sorted(check.iter_errors(document), key=lambda error: list(error.absolute_path))
    if errors:
        error = errors[0]
        location = "/".join(map(str, error.absolute_path)) or "<root>"
        raise ContractError(f"{label}: {location}: {error.message}")


def require_unique(values: list[Any], label: str) -> None:
    if len(values) != len(set(values)):
        raise ContractError(f"{label}: values must be unique")


def check_parameters(parameters: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    ids = [parameter["internalId"] for parameter in parameters]
    require_unique(ids, f"{label}: parameter internalIds")
    by_id = dict(zip(ids, parameters, strict=True))

    for parameter in parameters:
        parameter_type = parameter["type"]
        parameter_label = f"{label}: {parameter['internalId']}"
        if parameter_type == "PParameterGroup":
            missing = sorted(set(parameter["value"]) - set(by_id))
            if missing:
                raise ContractError(f"{parameter_label}: missing group references {missing}")
        elif parameter_type in {"PParameterEnum", "PParameterImageFormat"}:
            require_unique(parameter["possibleValues"], f"{parameter_label}: possibleValues")
            if parameter["value"] not in parameter["possibleValues"]:
                raise ContractError(f"{parameter_label}: default is not a possible value")
        elif parameter_type == "PParameterEnumList":
            require_unique(parameter["possibleValues"], f"{parameter_label}: possibleValues")
            invalid = sorted(set(parameter["value"]) - set(parameter["possibleValues"]))
            if invalid:
                raise ContractError(f"{parameter_label}: invalid defaults {invalid}")
        elif parameter_type in {"PParameterChoiceInt", "PParameterChoiceFloat"}:
            choices = parameter["possibleValues"]
            if not isinstance(choices, dict) or not all(isinstance(key, str) for key in choices):
                raise ContractError(f"{parameter_label}: possibleValues must be an object")
            expected = int if parameter_type.endswith("Int") else (int, float)
            if not all(isinstance(value, expected) and not isinstance(value, bool) for value in choices.values()):
                raise ContractError(f"{parameter_label}: possibleValues have the wrong numeric type")
            if parameter["value"] not in choices.values():
                raise ContractError(f"{parameter_label}: default is not a possible value")
        elif parameter_type == "PParameterDictStringList":
            value = parameter["value"]
            if not isinstance(value, dict) or not all(
                isinstance(key, str)
                and isinstance(items, list)
                and all(isinstance(item, str) for item in items)
                for key, items in value.items()
            ):
                raise ContractError(f"{parameter_label}: value must map strings to string arrays")
        elif parameter_type in {"PParameterRangeInt", "PParameterRangeFloat"}:
            minimum = parameter["minValue"]
            maximum = parameter["maxValue"]
            step = parameter["stepValue"]
            if minimum > maximum or not minimum <= parameter["value"] <= maximum or step == 0:
                raise ContractError(f"{parameter_label}: invalid range bounds, step, or default")
        elif parameter_type == "PParameterMinMaxDetectionSize":
            for axis in ("Width", "Height"):
                minimum = parameter[f"min{axis}Percentage"]
                maximum = parameter[f"max{axis}Percentage"]
                if not 0 <= minimum <= maximum <= 100:
                    raise ContractError(f"{parameter_label}: invalid {axis.lower()} percentages")
    return by_id


def check_scenario(document: dict[str, Any], label: str) -> None:
    parameters = check_parameters(document["parameters"], label)
    if document["type"] == "PScenarioIntrusion":
        references = [document["zoneId"]]
    else:
        references = [document["fromZoneId"], document["toZoneId"]]
    for reference in references:
        if reference not in parameters or not parameters[reference]["type"].startswith("PZone"):
            raise ContractError(f"{label}: {reference!r} does not reference a zone parameter")


def check_configuration(
    document: dict[str, Any], label: str, scenario_names: set[str]
) -> None:
    parameters = check_parameters(document["parameters"], label)
    scenario_parameter = parameters.get("scenarioNames")
    if scenario_parameter:
        missing = sorted(set(scenario_parameter["possibleValues"]) - scenario_names)
        if missing:
            raise ContractError(f"{label}: missing scenario names {missing}")


def expect_failure(action, label: str) -> None:
    try:
        action()
    except (ContractError, KeyError):
        return
    raise ContractError(f"negative test unexpectedly passed: {label}")


def run_negative_tests(checks: dict[str, Draft201909Validator], samples: dict[str, Any]) -> int:
    count = 0

    def structural(name: str, mutate, label: str) -> None:
        nonlocal count
        document = copy.deepcopy(samples[name])
        mutate(document)
        expect_failure(lambda: validate_json(document, checks[name], label), label)
        count += 1

    structural("event", lambda item: item["eventPayload"].pop("frameStart"), "alarmEnd missing frameStart")
    structural("event", lambda item: item.update(type="analyticEnd"), "known event with wrong payload")
    structural("event", lambda item: item.update(unexpected=True), "event with unknown field")
    structural("configuration", lambda item: item.update(schemaVersion=3), "wrong schema version")
    structural("configuration", lambda item: item["parameters"][0].update(type="UnknownParameter"), "unknown parameter")
    structural(
        "configuration",
        lambda item: item.update(scenarios=[samples["scenario"]]),
        "analytic scenario references must be names",
    )
    structural("scenario", lambda item: item.pop("toZoneId"), "crossing scenario missing toZoneId")

    configuration = copy.deepcopy(samples["configuration"])
    ranged = next(item for item in configuration["parameters"] if item["type"].startswith("PParameterRange"))
    ranged["value"] = ranged["maxValue"] + 1
    expect_failure(lambda: check_parameters(configuration["parameters"], "invalid range"), "range default")
    count += 1

    scenario = copy.deepcopy(samples["scenario"])
    scenario["toZoneId"] = "missing-zone"
    expect_failure(lambda: check_scenario(scenario, "invalid zone"), "missing zone reference")
    return count + 1


def main() -> int:
    if not PAPILLON_EDGE.is_dir():
        raise ContractError(f"Papillon Edge repository not found: {PAPILLON_EDGE}")

    checks = {
        "configuration": validator("analytic-configuration"),
        "scenario": validator("scenario"),
        "engine": validator("analytic-engine-configuration"),
        "event": validator("event"),
    }
    manifest = load(CORPUS / "manifest.json")
    documents = {"configuration": 0, "scenario": 0, "engine": 0, "event": 0}
    samples: dict[str, Any] = {}

    for profile, inventory in manifest["profiles"].items():
        scenario_documents = [load(MAGNETITE / profile / name) for name in inventory["scenarios"]]
        scenario_names = {document["name"] for document in scenario_documents}
        require_unique([document["name"] for document in scenario_documents], f"{profile}: scenario names")
        require_unique([document["internalId"] for document in scenario_documents], f"{profile}: scenario internalIds")
        for name, document in zip(inventory["scenarios"], scenario_documents, strict=True):
            label = f"{profile}/{name}"
            validate_json(document, checks["scenario"], label)
            check_scenario(document, label)
            documents["scenario"] += 1
            samples.setdefault("scenario", document)

        configurations = [load(MAGNETITE / profile / name) for name in inventory["analytics"]]
        require_unique([document["config"]["name"] for document in configurations], f"{profile}: analytic names")
        require_unique([document["config"]["id"] for document in configurations], f"{profile}: analytic ids")
        for name, document in zip(inventory["analytics"], configurations, strict=True):
            label = f"{profile}/{name}"
            validate_json(document, checks["configuration"], label)
            check_configuration(document, label, scenario_names)
            documents["configuration"] += 1
            if any(item["type"].startswith("PParameterRange") for item in document["parameters"]):
                samples.setdefault("configuration", document)

    for relative in manifest["engineDocuments"]:
        document = load(PAPILLON_EDGE / relative)
        validate_json(document, checks["engine"], relative)
        require_unique([item["config"]["name"] for item in document["analytics"]], f"{relative}: analytics")
        require_unique([item["name"] for item in document["scenarios"]], f"{relative}: scenarios")
        documents["engine"] += 1

    for event_type in manifest["eventTypes"]:
        document = load(CORPUS / "events" / f"{event_type}.json")
        validate_json(document, checks["event"], event_type)
        documents["event"] += 1
        if event_type == "alarmEnd":
            samples["event"] = document

    extension_event = copy.deepcopy(samples["event"])
    extension_event["type"] = "pluginDiagnostic"
    extension_event.pop("eventPayload")
    validate_json(extension_event, checks["event"], "extension event without payload")

    negative_count = run_negative_tests(checks, samples)
    print(
        "Contracts OK: "
        f"{documents['configuration']} configurations, {documents['scenario']} scenarios, "
        f"{documents['engine']} engine, {documents['event']} events, {negative_count} negative tests"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
