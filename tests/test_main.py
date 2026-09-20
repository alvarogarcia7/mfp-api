"""Tests for FastAPI endpoints."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Add backend to path for imports
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from main import app

client = TestClient(app)


class TestHealthCheck:
    """Test basic health checks."""

    def test_root_endpoint(self):
        """Test that root endpoint serves the app."""
        response = client.get("/")
        assert response.status_code in [200, 404]  # 200 if static files mounted, 404 if not


class TestOfflineFirstEndpoints:
    """Test offline-first API endpoints (no authentication)."""

    def test_status_endpoint(self):
        """Test /api/status endpoint."""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["mode"] == "offline-first"

    def test_food_instances_endpoint(self):
        """Test /api/food-instances endpoint."""
        response = client.get("/api/food-instances")
        assert response.status_code == 200
        data = response.json()
        assert "foods" in data
        assert "count" in data

    def test_food_entries_endpoint(self):
        """Test /api/food-entries endpoint."""
        response = client.get("/api/food-entries")
        assert response.status_code == 200
        data = response.json()
        assert "date" in data
        assert "meals" in data
        assert "has_data" in data

    def test_user_goals_endpoint(self):
        """Test /api/user-goals endpoint."""
        response = client.get("/api/user-goals")
        assert response.status_code == 200
        data = response.json()
        assert "calories" in data
        assert isinstance(data["calories"], (int, float))

    def test_today_summary_endpoint(self):
        """Test /api/today endpoint."""
        response = client.get("/api/today")
        assert response.status_code == 200
        data = response.json()
        assert "date" in data
        assert "goal_calories" in data
        assert "calories_eaten" in data

    def test_add_food_entry_validation(self):
        """Test /api/food-entries/add with missing data."""
        response = client.post("/api/food-entries/add", json={})
        assert response.status_code == 400
        assert "Missing" in response.json()["detail"]

    def test_add_valid_food_entry(self):
        """Test /api/food-entries/add with valid data."""
        payload = {
            "date": "2026-09-20",
            "meal": "lunch",
            "name": "Test Food",
            "calories": 100,
            "quantity": 1.0
        }
        response = client.post("/api/food-entries/add", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "entry" in data
        assert data["entry"]["name"] == "Test Food"


class TestDocumentation:
    """Test that API documentation is available."""

    def test_docs_endpoint(self):
        """Test that /docs endpoint exists."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_endpoint(self):
        """Test that /openapi.json endpoint exists."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "openapi" in response.json()
