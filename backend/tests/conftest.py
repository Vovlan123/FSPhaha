"""Тесты работают на отдельной временной SQLite-БД, демо-данные не трогаются."""
import os
import tempfile
from pathlib import Path

_db = Path(tempfile.mkdtemp(prefix="fsp_tests_")) / "test.db"
# По умолчанию — временная SQLite; TEST_DATABASE_URL позволяет прогнать те же тесты на PostgreSQL
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_db}"
os.environ["DEMO_EXPOSE_LINKS"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _register(client, email: str, role: str) -> dict:
    r = client.post("/api/auth/register", json={"email": email, "password": "password1", "role": role, "consent_pd": True})
    assert r.status_code == 201, r.text
    token = r.json()["dev_verify_link"].split("token=")[1]
    tok = client.get("/api/auth/verify", params={"token": token}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def register(client):
    return lambda email, role="candidate": _register(client, email, role)
