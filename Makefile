.PHONY: generate lint check test

generate:
	uv run scripts/generate_schemas.py

lint:
	uv run linkml-lint linkml

check: lint
	uv run scripts/generate_schemas.py --check

test: check
	uv run scripts/validate_contracts.py
