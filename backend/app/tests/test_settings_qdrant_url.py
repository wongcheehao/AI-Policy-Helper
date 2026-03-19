import qdrant_client


def test_qdrant_url_is_taken_from_env(monkeypatch, reload_settings_and_rag):
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

    _settings, rag = reload_settings_and_rag()
    _engine = rag.RAGEngine()

    assert seen["url"] == "http://example-qdrant:6333"

