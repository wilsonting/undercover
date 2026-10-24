import pytest
from fastapi.testclient import TestClient

from backend.db import connect, seed
from backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    """A client for the backend on a freshly seeded database of its own."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))
    with connect() as db:
        seed(db)
    return TestClient(app)
