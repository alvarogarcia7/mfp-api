.PHONY: help install install-prod run run-prod test test-cov typecheck clean lint format dev-setup mfp-download mfp-parse mfp-diary-download mfp-diary-parse polar-download polar-parse pre-commit-install

## Show help for all targets
help:
	@echo "MyFitnessPal API - Available targets:"
	@echo ""
	@echo "Server:"
	@echo "  make install      - Install all dependencies (dev + prod)"
	@echo "  make install-prod - Install only production dependencies"
	@echo "  make run          - Start development server (auto-reload, random port)"
	@echo "  make run-prod     - Start production server (4 workers, random port)"
	@echo ""
	@echo "Testing & Code Quality:"
	@echo "  make test         - Run test suite"
	@echo "  make test-cov     - Run tests with coverage report"
	@echo "  make typecheck   - Run mypy type checker"
	@echo "  make lint         - Check Python syntax"
	@echo "  make format       - Format code with black"
	@echo ""
	@echo "Data Management:"
	@echo "  make mfp-download       - Download MyFitnessPal food data (today)"
	@echo "  make mfp-parse          - Parse MyFitnessPal raw data into cache"
	@echo "  make mfp-diary-download - Download MyFitnessPal daily diary (today)"
	@echo "  make mfp-diary-parse    - Parse MyFitnessPal diary into cache"
	@echo "  make polar-download     - Download Polar Flow data (since last entry)"
	@echo "  make polar-parse        - Parse Polar Flow raw data into cache"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean              - Remove build artifacts"
	@echo "  make pre-commit-install - Install pre-commit hooks"
	@echo "  make dev-setup          - Setup development environment (includes pre-commit)"
	@echo ""
	@echo "Examples:"
	@echo "  make install && make run"
	@echo "  make mfp-download && make mfp-parse"
	@echo "  make mfp-diary-download && make mfp-diary-parse"
	@echo "  make polar-download && make polar-parse"

## Install all dependencies (dev + prod)
install:
	@echo "Installing dependencies with uv..."
	uv venv --python 3.13
	uv sync
	uv pip install --upgrade pip
	uv pip install -e .
	uv pip install -e ".[dev]"

## Install only production dependencies
install-prod:
	@echo "Installing production dependencies with uv..."
	uv pip install --upgrade pip
	uv pip install -e .

## Start the development server (auto-reload, random port)
run:
	echo "Starting MyFitnessPal API server on http://localhost:$$PORT"; \
	open http://0.0.0.0:15541; \
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 15541

## Start the development server (production mode, 4 workers)
run-prod:
	@PORT=$$(( (RANDOM % 8000) + 8000 )); \
	echo "Starting MyFitnessPal API server (production) on http://localhost:$$PORT"; \
	cd backend && uvicorn main:app --host 0.0.0.0 --port $$PORT --workers 4

## Run the test suite
test:
	@echo "Running tests..."
	uv run pytest tests/ -v --tb=short || (echo "No tests found or test execution failed" && exit 1)

## Run tests with coverage report
test-cov:
	@echo "Running tests with coverage..."
	uv run pytest tests/ -v --cov=backend --cov-report=html

## Run mypy type checker
typecheck:
	@echo "Running mypy type checker..."
	uv run mypy backend tests

## Check Python syntax of source files
lint:
	@echo "Checking Python syntax..."
	python3 -m py_compile backend/main.py backend/mfp_auth.py backend/vendor/mfp_client.py backend/vendor/diary.py
	@echo "✓ All files have valid syntax"

## Format code with black (requires: pip install black)
format:
	@echo "Note: Code formatting requires black. Install with: uv pip install black"
	@echo "Then run: black backend/ static/"

## Remove build artifacts and cache files
clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .coverage -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/ htmlcov/ .coverage || true
	@echo "✓ Cleaned"

## Download MyFitnessPal data (today)
mfp-download:
	@if [ ! -f .env.local ]; then \
		echo "Error: .env.local not found"; \
		echo "Copy .env.local.example to .env.local and add your credentials"; \
		exit 1; \
	fi
	@. ./.env.local; \
	if [ -n "$$MFP_SESSION_COOKIE" ]; then \
		echo "Downloading MyFitnessPal data using session cookie..."; \
		uv run python cli.py mfp fetch --cookie "$$MFP_SESSION_COOKIE" --last-two-weeks; \
	elif [ -n "$$MFP_USERNAME" ] && [ -n "$$MFP_PASSWORD" ]; then \
		echo "Downloading MyFitnessPal data using credentials..."; \
		uv run python cli.py mfp fetch --username "$$MFP_USERNAME" --password "$$MFP_PASSWORD" --last-two-weeks; \
	else \
		echo "Error: Missing MFP credentials in .env.local"; \
		echo "Set either MFP_SESSION_COOKIE or both MFP_USERNAME and MFP_PASSWORD"; \
		exit 1; \
	fi

## Parse MyFitnessPal raw data into cache
mfp-parse:
	@echo "Parsing MyFitnessPal data..."
	uv run python cli.py mfp parse --merge

## Download MyFitnessPal daily diary (today)
mfp-diary-download:
	@if [ ! -f .env.local ]; then \
		echo "Error: .env.local not found"; \
		echo "Copy .env.local.example to .env.local and add your credentials"; \
		exit 1; \
	fi
	@. ./.env.local; \
	if [ -n "$$MFP_SESSION_COOKIE" ]; then \
		echo "Downloading MyFitnessPal daily diary using session cookie..."; \
		uv run python -m backend.mfp.fetch_diary --cookie "$$MFP_SESSION_COOKIE" --today; \
	elif [ -n "$$MFP_USERNAME" ] && [ -n "$$MFP_PASSWORD" ]; then \
		echo "Downloading MyFitnessPal daily diary using credentials..."; \
		uv run python -m backend.mfp.fetch_diary --username "$$MFP_USERNAME" --password "$$MFP_PASSWORD" --today; \
	else \
		echo "Error: Missing MFP credentials in .env.local"; \
		echo "Set either MFP_SESSION_COOKIE or both MFP_USERNAME and MFP_PASSWORD"; \
		exit 1; \
	fi

## Parse MyFitnessPal diary data into cache
mfp-diary-parse:
	@echo "Parsing MyFitnessPal diary data..."
	@echo "Note: diary parse functionality to be implemented"

## Download Polar Flow data (incremental from last entry)
polar-download:
	@echo "Downloading Polar Flow data..."
	uv run python cli.py polar fetch --since-last-entry

## Parse Polar Flow raw data into cache
polar-parse:
	@echo "Parsing Polar Flow data..."
	uv run python cli.py polar parse --merge

## Install pre-commit hooks
pre-commit-install:
	@echo "Installing pre-commit hooks..."
	pre-commit install
	@echo "✓ Pre-commit hooks installed"

## Setup development environment (install deps)
dev-setup: install pre-commit-install
	@echo "Development environment ready!"
	@echo "Run 'make run' to start the server"
	@echo "Run 'make test' to run tests"
