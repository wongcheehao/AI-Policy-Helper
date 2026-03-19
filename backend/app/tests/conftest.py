import importlib
import sys

import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture
def reload_settings_and_rag():
    """
    Reload `app.settings` and `app.rag` after env changes.

    `settings = Settings()` is instantiated at import time, so tests that call
    `monkeypatch.setenv(...)` must reload modules to pick up the new env values.
    """

    def _reload():
        if "app.settings" in sys.modules:
            importlib.reload(sys.modules["app.settings"])
        else:
            import app.settings  # noqa: F401

        if "app.rag" in sys.modules:
            importlib.reload(sys.modules["app.rag"])
        else:
            import app.rag  # noqa: F401

        return sys.modules["app.settings"], sys.modules["app.rag"]

    return _reload
