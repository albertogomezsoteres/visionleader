# Single entry point for the common workflows. Run `make help` for the list.

PY ?= uv run
FD_IMAGE ?= fast-downward:latest

.DEFAULT_GOAL := help
.PHONY: help install lint format test test-planner serve planner-image benchmark-planner e2e-report clean

help:  ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install:  ## Create the environment from uv.lock (backend + dev tools)
	uv sync --frozen --extra dev
	uv run pre-commit install

lint:  ## Lint and check formatting
	$(PY) ruff check .
	$(PY) ruff format --check .

format:  ## Auto-fix lint issues and format the code
	$(PY) ruff check --fix .
	$(PY) ruff format .

test:  ## Run the unit and API tests (no Docker or GPU needed)
	$(PY) pytest -m "not planner"

test-planner:  ## Solve the evaluation problems with Fast Downward and check the optimal costs
	$(PY) pytest -m planner

serve:  ## Start the backend on http://localhost:8000
	$(PY) python scripts/start_api.py

planner-image:  ## Build the pinned Fast Downward image used by the planner
	docker build -t $(FD_IMAGE) docker/fast-downward

benchmark-planner:  ## Re-run the planner experiment (3 search configs x 12 problems)
	$(PY) python experiments/planner/evaluate_planner.py

e2e-report:  ## Rebuild the end-to-end validation CSVs from the telemetry log
	$(PY) python experiments/end_to_end/scripts/build_validation_csv.py

clean:  ## Remove caches and build artefacts
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov build dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
