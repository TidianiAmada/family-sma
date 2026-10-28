# Raccourcis du dépôt family_abm. Toutes les commandes passent par uv.
.PHONY: install format lint typecheck imports test test-fast check gate-v1 gate-v2 gate-v3

install:
	uv sync

format:
	uv run ruff format src tests

lint:
	uv run ruff format --check src tests
	uv run ruff check src tests

typecheck:
	uv run mypy src/

imports:
	uv run lint-imports

test:
	uv run pytest -q

# CI rapide (90 §4) : tout sauf slow et perf
test-fast:
	uv run pytest -q -m "not slow and not perf"

check: lint typecheck imports test-fast

# Portes de passage (90 §3) : scripts/gate.py est livré par T-019
gate-v1:
	uv run python scripts/gate.py v1

gate-v2:
	uv run python scripts/gate.py v2

gate-v3:
	uv run python scripts/gate.py v3
