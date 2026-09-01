# Papillon LinkML contracts

The production LinkML source is split by ownership:

- `linkml/common.yaml` defines shared scalar types.
- `linkml/parameters.yaml` defines every runtime-supported parameter and zone.
- `linkml/configuration.yaml` defines analytic, scenario, and engine documents.
- `linkml/events.yaml` defines canonical and extension events.

Generate and validate the checked-in JSON Schemas with:

```sh
uv sync --locked
make generate
make test
```

`scripts/validate_contracts.py` validates the Papillon Edge golden corpus and
checks cross-document constraints that JSON Schema cannot express, including
parameter references, scenario references, defaults, bounds, and uniqueness.
Set `PAPILLON_EDGE_ROOT` when the Papillon Edge repository is not a sibling of
this repository.

The four generated v2 schemas are published at the repository root so the
`release/v2.0` branch is directly addressable through `raw.githubusercontent.com`.
They are closed for known structures. Deliberately dynamic runtime maps
(`PParameterChoice*.possibleValues`, `PParameterDictStringList.value`, and
analytic-start parameter snapshots) are checked by the companion validator.
Unknown event names use the explicit `ExtensionEvent` branch; known names must
match their canonical payload class.

The underscore-named schemas and event examples are retained as the legacy v1
contract. The generated hyphenated schemas are the v2 public contract. Events
retain `eventVersion: 1` because their wire format has not changed.

`licensePlateFilter` remains `PParameterModelPath` for wire compatibility with
the current runtime. Its name is semantically surprising, but changing the type
would be a contract migration rather than a schema correction.
