import importlib
import os

import pytest
from fastapi.testclient import TestClient


def _reload_main(monkeypatch, env):
    for k in ("APP_ENV", "SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import app.main as main_mod
    importlib.reload(main_mod)
    return main_mod


def test_health(monkeypatch):
    main_mod = _reload_main(monkeypatch, {"APP_ENV": "development", "SECRET_KEY": "test-secret"})
    client = TestClient(main_mod.app)
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_missing_secret_raises(monkeypatch):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _reload_main(monkeypatch, {"APP_ENV": "development"})


def test_valid_config_loads(monkeypatch):
    main_mod = _reload_main(monkeypatch, {"APP_ENV": "development", "SECRET_KEY": "test-secret"})
    assert main_mod.settings.secret_key == "test-secret"
    assert main_mod.settings.app_env == "development"


def test_docs_available_in_development(monkeypatch):
    main_mod = _reload_main(monkeypatch, {"APP_ENV": "development", "SECRET_KEY": "test-secret"})
    client = TestClient(main_mod.app)
    r = client.get("/docs")
    assert r.status_code == 200


def test_docs_unavailable_outside_development(monkeypatch):
    main_mod = _reload_main(monkeypatch, {"APP_ENV": "production", "SECRET_KEY": "test-secret"})
    client = TestClient(main_mod.app)
    r = client.get("/docs")
    assert r.status_code == 404
