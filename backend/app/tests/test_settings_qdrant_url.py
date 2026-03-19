import importlib
import sys

import qdrant_client


def _reload_settings_and_rag():
    # settings are instantiated at import time, reload after env changes
    if "app.settings" in sys.modules:
        importlib.reload(sys.modules["app.settings"])
    else:
        import app.settings  # noqa: F401

    if "app.rag" in sys.modules:
        importlib.reload(sys.modules["app.rag"])
    else:
        import app.rag  # noqa: F401

    return sys.modules["app.settings"], sys.modules["app.rag"]


def test_qdrant_url_is_taken_from_env(monkeypatch):
    # Force the qdrant store path to execute, but keep it offline by mocking QdrantClient.
    monkeypatch.setenv("VECTOR_STORE", "qdrant")
    monkeypatch.setenv("QDRANT_URL", "http://example-qdrant:6333")
    monkeypatch.setenv("LLM_PROVIDER", "stub")

    # Patch qdrant_client.QdrantClient before importing app.rag.
    seen = {}

    class _FakeClient:
        def __init__(self, url: str, timeout: float):
            seen["url"] = url
            seen["timeout"] = timeout

        def get_collection(self, _name: str):
            return {"ok": True}

    monkeypatch.setattr(qdrant_client, "QdrantClient", _FakeClient)

    _settings, rag = _reload_settings_and_rag()
    _engine = rag.RAGEngine()

    assert seen["url"] == "http://example-qdrant:6333"

