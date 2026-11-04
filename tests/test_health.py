"""Контракт готовности по HTTP."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from logos_backend.app import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def migrate() -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    command.upgrade(config, "head")


def test_unmigrated_database_is_not_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = tmp_path / "logos.sqlite3"
    database.touch()
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(database))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is not ready"}


def test_missing_database_directory_is_not_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "missing" / "logos.sqlite3"))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is not ready"}


def test_migrated_database_is_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "logos.sqlite3"))
    migrate()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_returns_default_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "logos.sqlite3"))

    response = client.get("/unknown")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_documentation_endpoints_are_disabled(
    path: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "logos.sqlite3"))

    response = client.get(path)

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_method_not_allowed_uses_framework_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOGOS_DATABASE_PATH", str(tmp_path / "logos.sqlite3"))

    response = client.post("/health")

    assert response.status_code == 405
