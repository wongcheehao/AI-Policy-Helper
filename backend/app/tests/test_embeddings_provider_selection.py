import importlib
import sys
import types
import builtins

import pytest

from app.constants import (
    DEFAULT_EMBED_DIM,
    DEFAULT_SENTENCE_TRANSFORMER_MODEL,
    LOCAL_EMBEDDING_MODEL_NAME,
)


def _reload_settings_and_rag():
    if "app.settings" in sys.modules:
        importlib.reload(sys.modules["app.settings"])
    else:
        import app.settings  # noqa: F401

    if "app.rag" in sys.modules:
        importlib.reload(sys.modules["app.rag"])
    else:
        import app.rag  # noqa: F401

    return sys.modules["app.settings"], sys.modules["app.rag"]


def _set_common_env(monkeypatch, *, embedding_model: str):
    monkeypatch.setenv("EMBEDDING_MODEL", embedding_model)
    monkeypatch.setenv("VECTOR_STORE", "memory")
    monkeypatch.setenv("LLM_PROVIDER", "stub")


def _install_fake_sentence_transformers(monkeypatch, *, dim: int):
    """Install a fake `sentence_transformers` module to keep tests offline."""

    class _FakeModel:
        def get_sentence_embedding_dimension(self):
            return dim

        def encode(self, _text, normalize_embeddings: bool = False):
            assert normalize_embeddings is True
            return [0.0] * dim

    fake_st = types.SimpleNamespace(SentenceTransformer=lambda _name: _FakeModel())
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)


def _block_sentence_transformers_import(monkeypatch):
    """Block imports to simulate `sentence_transformers` not being installed."""
    sys.modules.pop("sentence_transformers", None)
    real_import = builtins.__import__

    def _blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "sentence_transformers" or name.startswith("sentence_transformers."):
            raise ImportError("blocked for test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)


def test_embedder_defaults_to_local_384(monkeypatch):
    """Keeps default runs offline: local embedder + matching store dimension."""
    _set_common_env(monkeypatch, embedding_model=LOCAL_EMBEDDING_MODEL_NAME)

    _settings, rag = _reload_settings_and_rag()
    engine = rag.RAGEngine()

    assert isinstance(engine.embedder, rag.LocalEmbedder)
    assert engine.embedder.dim == DEFAULT_EMBED_DIM
    assert engine.store.dim == DEFAULT_EMBED_DIM


@pytest.mark.parametrize(
    ("reported_dim", "embedding_model"),
    [
        (DEFAULT_EMBED_DIM, "all-MiniLM-L6-v2"),
        (768, "some-768d-model"),
    ],
)
def test_sentence_transformers_embedder_dim_matches_store_dim(
    monkeypatch, reported_dim: int, embedding_model: str
):
    """Prevents runtime failures: store dim must match the embedder’s true dimension."""
    _install_fake_sentence_transformers(monkeypatch, dim=reported_dim)
    _set_common_env(monkeypatch, embedding_model=embedding_model)

    _settings, rag = _reload_settings_and_rag()
    engine = rag.RAGEngine()

    assert isinstance(engine.embedder, rag.SentenceTransformerEmbedder)
    assert engine.embedder.dim == reported_dim
    assert engine.store.dim == reported_dim


def test_local_embedder_does_not_require_sentence_transformers(monkeypatch):
    """Default stub-first mode must start without optional heavy embedding deps installed."""
    _set_common_env(monkeypatch, embedding_model=LOCAL_EMBEDDING_MODEL_NAME)
    _block_sentence_transformers_import(monkeypatch)

    _settings, rag = _reload_settings_and_rag()
    engine = rag.RAGEngine()

    assert isinstance(engine.embedder, rag.LocalEmbedder)


def test_default_embedding_model_uses_sentence_transformers(monkeypatch):
    """Ensures default settings use real embeddings (no silent fallback to stub embedder)."""
    _install_fake_sentence_transformers(monkeypatch, dim=DEFAULT_EMBED_DIM)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.setenv("VECTOR_STORE", "memory")
    monkeypatch.setenv("LLM_PROVIDER", "stub")

    _settings, rag = _reload_settings_and_rag()
    engine = rag.RAGEngine()

    assert _settings.settings.embedding_model == DEFAULT_SENTENCE_TRANSFORMER_MODEL
    assert isinstance(engine.embedder, rag.SentenceTransformerEmbedder)

