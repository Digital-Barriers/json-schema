# Papillon LinkML go/no-go prototype

This prototype tests the two risky parts of replacing the hand-written JSON
Schemas with LinkML-generated schemas:

1. a polymorphic `Parameter` hierarchy discriminated by existing values such
   as `PParameterRangeInt`;
2. an event union in which `type: alarmEnd` requires `AlarmEndPayload`.

The LinkML source is `papillon-contract.yaml`. `generate.py` writes the two
files under `generated` directly through the LinkML generator API; the output
is not patched or post-processed. Dependencies and Python are pinned by
`pyproject.toml` and `uv.lock`.

Valid cases are read from the sibling `papillon-edge` repository so its Task 1
contract corpus remains authoritative. Set `PAPILLON_EDGE_ROOT` when the repos
are not siblings. Deliberately invalid documents live in `fixtures/invalid`.

Run the checkpoint:

```bash
uv sync --locked
make test
```

Regenerate after changing the LinkML source:

```bash
make generate
```

## Result

LinkML 1.11.1 generates a working JSON Schema `oneOf` for both hierarchies.
Each branch has a discriminator `const`, a matching payload or parameter
shape, and `additionalProperties: false`. The synthetic composition root must
remain open because LinkML's `--closed` option closes that property-less root
before its `$ref` branches are evaluated; the referenced branches themselves
are closed by the generator.

LinkML rules were also evaluated as an alternative event representation. In
1.11.1, rules generated the `type` `if` condition but discarded the class
range on `eventPayload`, producing an unconstrained `then`. The class-based
`oneOf` is therefore the supported design for this contract.
