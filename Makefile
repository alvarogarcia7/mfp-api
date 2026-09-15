.PHONY: help install install-prod run run-prod test test-cov clean lint format dev-setup

## Show help for all targets
help:
	@echo "MyFitnessPal API - Available targets:"
	@echo ""
	@echo "  make install      - Install all dependencies (dev + prod)"
	@echo "  make install-prod - Install only production dependencies"
	@echo "  make run          - Start development server (auto-reload, random port)"
	@echo "  make run-prod     - Start production server (4 workers, random port)"
	@echo "  make test         - Run test suite"
	@echo "  make test-cov     - Run tests with coverage report"
	@echo "  make lint         - Check Python syntax"
	@echo "  make format       - Format code with black"
	@echo "  make clean        - Remove build artifacts"
	@echo "  make dev-setup    - Setup development environment"
	@echo ""
	@echo "Examples:"
	@echo "  make install && make run"
	@echo "  make test"
	@echo "  make clean"

## Install all dependencies (dev + prod)
install:
	@echo "Installing dependencies with uv..."
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
	@PORT=$$(( (RANDOM % 8000) + 8000 )); \
	echo "Starting MyFitnessPal API server on http://localhost:$$PORT"; \
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port $$PORT

## Start the development server (production mode, 4 workers)
run-prod:
	@PORT=$$(( (RANDOM % 8000) + 8000 )); \
	echo "Starting MyFitnessPal API server (production) on http://localhost:$$PORT"; \
	cd backend && uvicorn main:app --host 0.0.0.0 --port $$PORT --workers 4

## Run the test suite
test:
	@echo "Running tests..."
	pytest tests/ -v --tb=short || (echo "No tests found or test execution failed" && exit 1)

## Run tests with coverage report
test-cov:
	@echo "Running tests with coverage..."
	pytest tests/ -v --cov=backend --cov-report=html

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

## Setup development environment (install deps)
dev-setup: install
	@echo "Development environment ready!"
	@echo "Run 'make run' to start the server"
	@echo "Run 'make test' to run tests"
