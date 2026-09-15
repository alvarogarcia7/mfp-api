#!/bin/bash
# MyFitnessPal API - Quick start script

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed. Please install it first:"
    echo "  pip install uv"
    exit 1
fi

# Install dependencies
echo "Installing dependencies with uv..."
uv pip install -e . -e ".[dev]"

# Start the server with random port
PORT=$(( (RANDOM % 8000) + 8000 ))
echo "Starting server on http://localhost:$PORT"
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port $PORT
