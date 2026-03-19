import time, os, math, json, hashlib
from typing import List, Dict, Tuple
import numpy as np
from .constants import (
    DEFAULT_CONTEXT_PREVIEW_CHARS,
    DEFAULT_EMBED_DIM,
    LOCAL_EMBEDDING_MODEL_NAME,
    OPENROUTER_BASE_URL,
    QDRANT_TIMEOUT_S,
)
from .settings import settings
from .ingest import chunk_text, doc_hash
from qdrant_client import QdrantClient, models as qm

# ---- Simple local embedder (deterministic) ----
def _tokenize(s: str) -> List[str]:
    return [t.lower() for t in s.split()]

class LocalEmbedder:
    def __init__(self, dim: int = DEFAULT_EMBED_DIM):
        self.dim = dim

    def embed(self, text: str) -> np.ndarray:
        # Hash-based repeatable pseudo-embedding
        h = hashlib.sha1(text.encode("utf-8")).digest()
        rng_seed = int.from_bytes(h[:8], "big") % (2**32-1)
        rng = np.random.default_rng(rng_seed)
        v = rng.standard_normal(self.dim).astype("float32")
        # L2 normalize
        v = v / (np.linalg.norm(v) + 1e-9)
        return v


class SentenceTransformerEmbedder:
    """
    Embedding backend powered by Sentence Transformers (SBERT).

    Used when `EMBEDDING_MODEL` is set to a real SBERT model name (e.g.
    `all-MiniLM-L6-v2`). This produces semantic embeddings for chunks and queries,
    enabling meaningful vector retrieval (unlike the deterministic hash embedder).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Args:
            model_name: Hugging Face / Sentence-Transformers model identifier.
        """
        try:
            from sentence_transformers import SentenceTransformer  # optional heavy dependency
        except ImportError as e:
            raise RuntimeError(
                "Sentence-transformers is required when EMBEDDING_MODEL is set to a "
                "Sentence Transformers model name. Install it with "
                "`pip install -U sentence-transformers` (or add it to backend/requirements.txt), "
                f"or set EMBEDDING_MODEL={LOCAL_EMBEDDING_MODEL_NAME} for offline stub-first development."
            ) from e

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dim = int(self.model.get_sentence_embedding_dimension())

    def embed(self, text: str) -> np.ndarray:
        """Return a normalized float32 embedding vector for `text`."""
        v = self.model.encode(text, normalize_embeddings=True)
        return np.asarray(v, dtype="float32")


def _build_embedder():
    """
    Select embedding backend based on configuration.

    - `EMBEDDING_MODEL=local-384` uses `LocalEmbedder` (offline + deterministic).
    - Any other value is treated as a Sentence-Transformers model name and uses
      `SentenceTransformerEmbedder`.
    """
    # Default stays local/offline unless EMBEDDING_MODEL requests a real model.
    name = (settings.embedding_model or LOCAL_EMBEDDING_MODEL_NAME).strip()
    if name == LOCAL_EMBEDDING_MODEL_NAME:
        return LocalEmbedder(dim=DEFAULT_EMBED_DIM)
    return SentenceTransformerEmbedder(model_name=name)

# ---- Vector store abstraction ----
class InMemoryStore:
    def __init__(self, dim: int = DEFAULT_EMBED_DIM):
        self.dim = dim
        self.vecs: List[np.ndarray] = []
        self.meta: List[Dict] = []
        self._hashes = set()

    def upsert(self, vectors: List[np.ndarray], metadatas: List[Dict]):
        for v, m in zip(vectors, metadatas):
            h = m.get("hash")
            if h and h in self._hashes:
                continue
            self.vecs.append(v.astype("float32"))
            self.meta.append(m)
            if h:
                self._hashes.add(h)

    def search(self, query: np.ndarray, k: int = 4) -> List[Tuple[float, Dict]]:
        if not self.vecs:
            return []
        A = np.vstack(self.vecs)  # [N, d]
        q = query.reshape(1, -1)  # [1, d]
        # cosine similarity
        sims = (A @ q.T).ravel() / (np.linalg.norm(A, axis=1) * (np.linalg.norm(q) + 1e-9) + 1e-9)
        idx = np.argsort(-sims)[:k]
        return [(float(sims[i]), self.meta[i]) for i in idx]

class QdrantStore:
    def __init__(self, collection: str, dim: int = DEFAULT_EMBED_DIM):
        self.client = QdrantClient(url=settings.qdrant_url, timeout=QDRANT_TIMEOUT_S)
        self.collection = collection
        self.dim = dim
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            self.client.get_collection(self.collection)
        except Exception:
            self.client.recreate_collection(
                collection_name=self.collection,
                vectors_config=qm.VectorParams(size=self.dim, distance=qm.Distance.COSINE)
            )

    def upsert(self, vectors: List[np.ndarray], metadatas: List[Dict]):
        points = []
        for i, (v, m) in enumerate(zip(vectors, metadatas)):
            points.append(qm.PointStruct(id=m.get("id") or m.get("hash") or i, vector=v.tolist(), payload=m))
        self.client.upsert(collection_name=self.collection, points=points)

    def search(self, query: np.ndarray, k: int = 4) -> List[Tuple[float, Dict]]:
        res = self.client.search(
            collection_name=self.collection,
            query_vector=query.tolist(),
            limit=k,
            with_payload=True
        )
        out = []
        for r in res:
            out.append((float(r.score), dict(r.payload)))
        return out

# ---- LLM provider ----
class StubLLM:
    def generate(self, query: str, contexts: List[Dict]) -> str:
        lines = [f"Answer (stub): Based on the following sources:"]
        for c in contexts:
            sec = c.get("section") or "Section"
            lines.append(f"- {c.get('title')} — {sec}")
        lines.append("Summary:")
        # naive summary of top contexts
        joined = " ".join([c.get("text", "") for c in contexts])
        lines.append(
            joined[:DEFAULT_CONTEXT_PREVIEW_CHARS]
            + ("..." if len(joined) > DEFAULT_CONTEXT_PREVIEW_CHARS else "")
        )
        return "\n".join(lines)

class OpenRouterLLM:
    def __init__(self, api_key: str, model: str = "openai/gpt-4o-mini"):
        from openai import OpenAI
        self.client = OpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
        )
        self.model = model

    def generate(self, query: str, contexts: List[Dict]) -> str:
        prompt = f"You are a helpful company policy assistant. Cite sources by title and section when relevant.\nQuestion: {query}\nSources:\n"
        for c in contexts:
            prompt += (
                f"- {c.get('title')} | {c.get('section')}\n"
                f"{c.get('text')[:DEFAULT_CONTEXT_PREVIEW_CHARS]}\n---\n"
            )
        prompt += "Write a concise, accurate answer grounded in the sources. If unsure, say so."
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role":"user","content":prompt}],
            temperature=0.1
        )
        return resp.choices[0].message.content

# ---- RAG Orchestrator & Metrics ----
class Metrics:
    def __init__(self):
        self.t_retrieval = []
        self.t_generation = []

    def add_retrieval(self, ms: float):
        self.t_retrieval.append(ms)

    def add_generation(self, ms: float):
        self.t_generation.append(ms)

    def summary(self) -> Dict:
        avg_r = sum(self.t_retrieval)/len(self.t_retrieval) if self.t_retrieval else 0.0
        avg_g = sum(self.t_generation)/len(self.t_generation) if self.t_generation else 0.0
        return {
            "avg_retrieval_latency_ms": round(avg_r, 2),
            "avg_generation_latency_ms": round(avg_g, 2),
        }

class RAGEngine:
    def __init__(self):
        self.embedder = _build_embedder()
        embed_dim = int(getattr(self.embedder, "dim", DEFAULT_EMBED_DIM))
        # Vector store selection
        if settings.vector_store == "qdrant":
            try:
                self.store = QdrantStore(collection=settings.collection_name, dim=embed_dim)
            except Exception:
                self.store = InMemoryStore(dim=embed_dim)
        else:
            self.store = InMemoryStore(dim=embed_dim)

        # LLM selection
        if settings.llm_provider == "openrouter" and settings.openrouter_api_key:
            try:
                self.llm = OpenRouterLLM(
                    api_key=settings.openrouter_api_key,
                    model=settings.llm_model,
                )
                self.llm_name = f"openrouter:{settings.llm_model}"
            except Exception:
                self.llm = StubLLM()
                self.llm_name = "stub"
        else:
            self.llm = StubLLM()
            self.llm_name = "stub"

        self.metrics = Metrics()
        self._doc_titles = set()
        self._chunk_count = 0

    def ingest_chunks(self, chunks: List[Dict]) -> Tuple[int, int]:
        vectors = []
        metas = []
        doc_titles_before = set(self._doc_titles)

        for ch in chunks:
            text = ch["text"]
            h = doc_hash(text)
            # Qdrant point IDs must be either unsigned integers or UUIDs.
            # Our `doc_hash()` returns a hex string, so we convert it into a deterministic
            # 64-bit unsigned integer ID for compatibility.
            point_id = int(h[:16], 16)
            meta = {
                "id": point_id,
                "hash": h,
                "title": ch["title"],
                "section": ch.get("section"),
                "text": text,
            }
            v = self.embedder.embed(text)
            vectors.append(v)
            metas.append(meta)
            self._doc_titles.add(ch["title"])
            self._chunk_count += 1

        self.store.upsert(vectors, metas)
        return (len(self._doc_titles) - len(doc_titles_before), len(metas))

    def retrieve(self, query: str, k: int = 4) -> List[Dict]:
        t0 = time.time()
        qv = self.embedder.embed(query)
        results = self.store.search(qv, k=k)
        self.metrics.add_retrieval((time.time()-t0)*1000.0)
        return [meta for score, meta in results]

    def generate(self, query: str, contexts: List[Dict]) -> str:
        t0 = time.time()
        answer = self.llm.generate(query, contexts)
        self.metrics.add_generation((time.time()-t0)*1000.0)
        return answer

    def stats(self) -> Dict:
        m = self.metrics.summary()
        return {
            "total_docs": len(self._doc_titles),
            "total_chunks": self._chunk_count,
            "embedding_model": settings.embedding_model,
            "llm_model": self.llm_name,
            **m
        }

# ---- Helpers ----
def build_chunks_from_docs(docs: List[Dict], chunk_size: int, overlap: int) -> List[Dict]:
    out = []
    for d in docs:
        for ch in chunk_text(d["text"], chunk_size, overlap):
            out.append({"title": d["title"], "section": d["section"], "text": ch})
    return out
