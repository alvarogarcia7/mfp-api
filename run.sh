#!/bin/bash
# MyFitnessPal API - Quick start script

# Install dependencies if not already done
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed. Please install it first:"
    echo "  pip install uv"
    exit 1
fi

# Install dependencies
echo "Installing dependencies with uv..."
uv pip install -e . -e ".[dev]"

# Start the server
echo "Starting server on http://localhost:8000"
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
