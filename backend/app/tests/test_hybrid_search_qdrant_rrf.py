import qdrant_client


def test_qdrant_hybrid_search_uses_rrf_fusion(monkeypatch, reload_settings_and_rag):
    """Hybrid search should run dense+sparse searches and fuse via RRF."""
    monkeypatch.setenv("VECTOR_STORE", "qdrant")
    monkeypatch.setenv("HYBRID_SEARCH_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    # Keep this test focused on hybrid retrieval wiring. Reranking can change
    # the candidate size passed to the store, which would obscure what we
    # are asserting here.
    monkeypatch.setenv("RERANKING_ENABLED", "false")

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

        def search_batch(self, **kwargs):
            seen["search_batch_kwargs"] = kwargs
            # Returning empty responses keeps the test offline; RRF should still
            # be invoked with the two response lists.
            return [[], []]

    monkeypatch.setattr(qdrant_client, "QdrantClient", _FakeClient)

    # Validate that we use Qdrant's reference reciprocal rank fusion helper.
    from qdrant_client.hybrid import fusion as fusion_mod

    def _fake_rrf(responses, limit=10):
        seen["rrf"] = {"limit": limit, "responses_len": len(responses)}
        return []

    monkeypatch.setattr(fusion_mod, "reciprocal_rank_fusion", _fake_rrf)

    _settings, rag = reload_settings_and_rag()
    engine = rag.RAGEngine()

    _ = engine.retrieve("bulky surcharge", k=5)

    assert "search_batch_kwargs" in seen
    assert len(seen["search_batch_kwargs"]["requests"]) == 2

    req0, req1 = seen["search_batch_kwargs"]["requests"]
    assert req0.vector.name == rag.QDRANT_DENSE_VECTOR_NAME
    assert req1.vector.name == rag.QDRANT_SPARSE_VECTOR_NAME

    assert seen["rrf"]["limit"] == 5
    assert seen["rrf"]["responses_len"] == 2

