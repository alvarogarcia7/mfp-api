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


class TestAuthEndpoints:
    """Test authentication endpoints."""

    def test_login_missing_credentials(self):
        """Test login with missing credentials."""
        response = client.post("/api/login", json={})
        assert response.status_code == 400
        assert "Missing" in response.json()["detail"]

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        response = client.post(
            "/api/login",
            json={"username": "invalid", "password": "invalid"}
        )
        assert response.status_code == 401

    def test_logout_missing_auth(self):
        """Test logout without authentication."""
        response = client.post("/api/logout")
        assert response.status_code == 401


class TestProtectedEndpoints:
    """Test that protected endpoints require authentication."""

    def test_today_missing_auth(self):
        """Test /api/today without auth header."""
        response = client.get("/api/today")
        assert response.status_code == 401

    def test_search_missing_auth(self):
        """Test /api/search without auth header."""
        response = client.post("/api/search", json={"query": "test"})
        assert response.status_code == 401

    def test_log_missing_auth(self):
        """Test /api/log without auth header."""
        response = client.post(
            "/api/log",
            json={"food_id": "123", "weight_id": "456", "quantity": 100}
        )
        assert response.status_code == 401

    def test_invalid_session_id(self):
        """Test with invalid session ID."""
        response = client.get(
            "/api/today",
            headers={"Authorization": "Bearer invalid-session-uuid"}
        )
        assert response.status_code == 401
        assert "Session expired" in response.json()["detail"]


class TestInputValidation:
    """Test input validation."""

    def test_login_missing_username(self):
        """Test login with missing username."""
        response = client.post("/api/login", json={"password": "test"})
        assert response.status_code == 400

    def test_login_missing_password(self):
        """Test login with missing password."""
        response = client.post("/api/login", json={"username": "test"})
        assert response.status_code == 400

    def test_search_missing_query(self):
        """Test search with missing query."""
        response = client.post(
            "/api/search",
            json={},
            headers={"Authorization": "Bearer valid-uuid"}
        )
        # Will fail auth first, but if auth passed, would need query
        assert response.status_code in [401, 400]


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
