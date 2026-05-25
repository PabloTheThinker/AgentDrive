.PHONY: dev test lint format check clean install

# One-command bring-up for contributors. See DEVELOPERS.md.
dev:
	@./scripts/dev-bringup.sh

install:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

check: lint
	ruff format --check .
	pytest

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
