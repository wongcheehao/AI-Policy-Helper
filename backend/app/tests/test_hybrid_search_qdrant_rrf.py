import qdrant_client


def test_qdrant_hybrid_search_uses_rrf_fusion(monkeypatch, reload_settings_and_rag):
    """Hybrid search should call Qdrant query_points with FusionQuery(RRF) + prefetch."""
    monkeypatch.setenv("VECTOR_STORE", "qdrant")
    monkeypatch.setenv("HYBRID_SEARCH_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "stub")

    seen = {}

    class _FakeClient:
        def __init__(self, url: str, timeout: float):
            pass

        def get_collection(self, _name: str):
            raise Exception("force recreate")

        def recreate_collection(self, **kwargs):
            seen["recreate_kwargs"] = kwargs

        def upsert(self, **_kwargs):
            return None

        def query_points(self, **kwargs):
            seen["query_kwargs"] = kwargs

            class _Resp:
                points = []

            return _Resp()

    monkeypatch.setattr(qdrant_client, "QdrantClient", _FakeClient)

    _settings, rag = reload_settings_and_rag()
    engine = rag.RAGEngine()

    _ = engine.retrieve("bulky surcharge", k=5)

    assert "query_kwargs" in seen
    assert seen["query_kwargs"]["query"].fusion == rag.qm.Fusion.RRF
    assert len(seen["query_kwargs"]["prefetch"]) == 2

