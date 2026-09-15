.PHONY: help install run test clean lint format

help:
	@echo "MyFitnessPal API - Available targets:"
	@echo "  make install  - Install dependencies using uv"
	@echo "  make run      - Start the development server"
	@echo "  make test     - Run tests"
	@echo "  make clean    - Remove build artifacts and cache"
	@echo "  make lint     - Run code linting (syntax check)"
	@echo "  make format   - Format code with black"

install:
	@echo "Installing dependencies with uv..."
	uv pip install --upgrade pip
	uv pip install -e .
	uv pip install -e ".[dev]"

install-prod:
	@echo "Installing production dependencies with uv..."
	uv pip install --upgrade pip
	uv pip install -e .

run:
	@echo "Starting MyFitnessPal API server..."
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

run-prod:
	@echo "Starting MyFitnessPal API server (production)..."
	cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

test:
	@echo "Running tests..."
	pytest tests/ -v --tb=short || (echo "No tests found or test execution failed" && exit 1)

test-cov:
	@echo "Running tests with coverage..."
	pytest tests/ -v --cov=backend --cov-report=html

lint:
	@echo "Checking Python syntax..."
	python3 -m py_compile backend/main.py backend/mfp_auth.py backend/vendor/mfp_client.py backend/vendor/diary.py
	@echo "✓ All files have valid syntax"

format:
	@echo "Note: Code formatting requires black. Install with: uv pip install black"
	@echo "Then run: black backend/ static/"

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

dev-setup: install
	@echo "Development environment ready!"
	@echo "Run 'make run' to start the server"
	@echo "Run 'make test' to run tests"
