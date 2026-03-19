import time, os, math, json, hashlib, zlib
from typing import List, Dict, Tuple
import numpy as np
from .constants import (
    DEFAULT_CONTEXT_PREVIEW_CHARS,
    DEFAULT_EMBED_DIM,
    LOCAL_EMBEDDING_MODEL_NAME,
    OPENROUTER_BASE_URL,
    QDRANT_DENSE_VECTOR_NAME,
    QDRANT_SPARSE_VECTOR_NAME,
    QDRANT_TIMEOUT_S,
    SPARSE_HASH_DIM,
)
from .settings import settings
from .ingest import chunk_text, doc_hash
from qdrant_client import QdrantClient, models as qm

# ---- Simple local embedder (deterministic) ----
def _tokenize(s: str) -> List[str]:
    return [t.lower() for t in s.split()]

def _sparse_encode(text: str) -> qm.SparseVector:
    """
    Produce a lightweight sparse vector for keyword-style matching.

    We hash tokens into a fixed-sized index space (no external model required).
    This is not a full BM25 implementation, but it captures exact-token signals
    which complement dense semantic search in hybrid retrieval.
    """
    counts: Dict[int, float] = {}
    for t in _tokenize(text):
        if not t:
            continue
        idx = (zlib.adler32(t.encode("utf-8")) & 0xFFFFFFFF) % SPARSE_HASH_DIM
        counts[idx] = counts.get(idx, 0.0) + 1.0

    if not counts:
        return qm.SparseVector(indices=[], values=[])

    indices = sorted(counts.keys())
    values = [float(counts[i]) for i in indices]
    return qm.SparseVector(indices=indices, values=values)

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

    def search(
        self, query: np.ndarray, k: int = 4, *, query_text: str | None = None
    ) -> List[Tuple[float, Dict]]:
        if not self.vecs:
            return []
        A = np.vstack(self.vecs)  # [N, d]
        q = query.reshape(1, -1)  # [1, d]
        # cosine similarity
        sims = (A @ q.T).ravel() / (np.linalg.norm(A, axis=1) * (np.linalg.norm(q) + 1e-9) + 1e-9)
        idx = np.argsort(-sims)[:k]
        return [(float(sims[i]), self.meta[i]) for i in idx]

class QdrantStore:
    """
    Qdrant-backed vector store supporting hybrid retrieval.

    Hybrid mode stores both:
    - a dense embedding in the `dense` vector
    - a lightweight keyword/sparse vector in the `sparse` vector

    Query-time hybrid retrieval uses Qdrant's `FusionQuery` with `Fusion.RRF`
    to combine dense + sparse candidate sets in a rank-order stable way.
    """

    def __init__(self, collection: str, dim: int = DEFAULT_EMBED_DIM):
        self.client = QdrantClient(url=settings.qdrant_url, timeout=QDRANT_TIMEOUT_S)
        self.collection = collection
        self.dim = dim
        self._ensure_collection()

    def _ensure_collection(self):
        """
        Ensure the Qdrant collection exists with the correct vector configs.

        We recreate the collection if:
        - it doesn't exist (or Qdrant rejects the request), or
        - it doesn't match our expected schema:
          - named dense vector called `dense`
          - named sparse vector called `sparse`
          - dense vector dimension matches `self.dim`

        Why this matters:
        - Docker uses a persistent `qdrant_data` volume between test runs.
          If an older run created `policy_helper` with the *default* (unnamed)
          vector config, then our upsert would fail with "Not existing vector name error: dense".
        """
        try:
            info = self.client.get_collection(self.collection)
        except Exception:
            info = None

        recreate = info is None
        if info is not None:
            params = getattr(getattr(info, "config", None), "params", None)
            vectors = getattr(params, "vectors", None)
            sparse_vectors = getattr(params, "sparse_vectors", None)

            # Unnamed vectors are represented as a single VectorParams object.
            dense_ok = (
                isinstance(vectors, dict)
                and QDRANT_DENSE_VECTOR_NAME in vectors
                and int(getattr(vectors[QDRANT_DENSE_VECTOR_NAME], "size", -1)) == self.dim
            )
            sparse_ok = (
                isinstance(sparse_vectors, dict)
                and QDRANT_SPARSE_VECTOR_NAME in sparse_vectors
            )

            recreate = not (dense_ok and sparse_ok)

        if recreate:
            self.client.recreate_collection(
                collection_name=self.collection,
                vectors_config={
                    QDRANT_DENSE_VECTOR_NAME: qm.VectorParams(
                        size=self.dim, distance=qm.Distance.COSINE
                    )
                },
                # Hybrid retrieval requires the `sparse` vector to exist as well.
                sparse_vectors_config={QDRANT_SPARSE_VECTOR_NAME: qm.SparseVectorParams()},
            )

    def upsert(self, vectors: List[np.ndarray], metadatas: List[Dict]):
        """
        Upsert dense + sparse vectors and store retrieval payload.

        Notes:
        - `metadatas[i]["text"]` is used to build the sparse keyword signal.
          This intentionally matches the "chunked" text, so retrieval uses
          the same token boundaries we indexed.
        - Qdrant point IDs must be either unsigned integers or UUIDs.
          Our ingestion pipeline provides a deterministic 64-bit int `id`.
        """
        points = []
        for i, (v, m) in enumerate(zip(vectors, metadatas)):
            sparse = _sparse_encode(m.get("text", ""))
            points.append(
                qm.PointStruct(
                    id=m.get("id") or m.get("hash") or i,
                    vector={
                        QDRANT_DENSE_VECTOR_NAME: v.tolist(),
                        QDRANT_SPARSE_VECTOR_NAME: sparse,
                    },
                    payload=m,
                )
            )
        self.client.upsert(collection_name=self.collection, points=points)

    def search(self, query: np.ndarray, k: int = 4, *, query_text: str | None = None) -> List[Tuple[float, Dict]]:
        """
        Retrieve top-k chunks from Qdrant.

        If `settings.hybrid_search_enabled` is true and `query_text` is provided,
        we issue a single `query_points` request with two `prefetch` blocks:
        - dense prefetch: dense embedding similarity
        - sparse prefetch: hashed keyword signals

        Qdrant's RRF (`Fusion.RRF`) then fuses candidates from both prefetch
        streams into a final ranked list.
        """
        # NOTE: we intentionally avoid `query_points + FusionQuery` here because
        # `qdrant-client==1.9.2` (used by this repo) does not expose the
        # corresponding Python model classes (`Prefetch`, `FusionQuery`, etc).
        # Instead we:
        # 1) run dense + sparse searches (top-N) via `search_batch()`
        # 2) fuse them using Qdrant's reference RRF implementation
        #    (`qdrant_client.hybrid.fusion.reciprocal_rank_fusion`)

        if settings.hybrid_search_enabled and query_text:
            candidate_limit = max(k * 4, 20)
            dense_req = qm.SearchRequest(
                vector=qm.NamedVector(name=QDRANT_DENSE_VECTOR_NAME, vector=query.tolist()),
                limit=candidate_limit,
                with_payload=True,
            )
            sparse_req = qm.SearchRequest(
                vector=qm.NamedSparseVector(
                    name=QDRANT_SPARSE_VECTOR_NAME, vector=_sparse_encode(query_text)
                ),
                limit=candidate_limit,
                with_payload=True,
            )

            dense_resp, sparse_resp = self.client.search_batch(
                collection_name=self.collection, requests=[dense_req, sparse_req]
            )

            from qdrant_client.hybrid.fusion import reciprocal_rank_fusion

            fused = reciprocal_rank_fusion(
                responses=[dense_resp, sparse_resp], limit=k
            )
            return [(float(p.score), dict(p.payload)) for p in fused]

        # Dense-only retrieval (named vector) for when hybrid is disabled.
        dense_only = self.client.search(
            collection_name=self.collection,
            query_vector=qm.NamedVector(name=QDRANT_DENSE_VECTOR_NAME, vector=query.tolist()),
            limit=k,
            with_payload=True,
        )
        return [(float(p.score), dict(p.payload)) for p in dense_only]

# ---- Reranking (post-retrieval) ----
class StubReranker:
    """
    Deterministic, offline-friendly reranker.

    Purpose:
    - Reorder retrieved chunks by a cheap query<->chunk token-overlap signal.
    - Keep behavior stable for tests and local development (no model downloads).

    Scoring:
    - Tokenize the query and count how many of those tokens appear in the chunk.
    - Tie-break using the original candidate order to keep results stable.
    """

    def rerank(
        self, query: str, candidates: List[Tuple[float, Dict]]
    ) -> List[Tuple[float, Dict]]:
        q_tokens = _tokenize(query)
        if not q_tokens:
            # Nothing to match: preserve original order.
            return candidates

        q_set = set(q_tokens)

        def _score(meta: Dict) -> float:
            passage = meta.get("text", "") or ""
            p_tokens = set(_tokenize(passage))
            # Count query tokens (including duplicates in the query) that appear in the passage.
            return float(sum(1 for t in q_tokens if t in p_tokens))

        scored: List[Tuple[float, int, Dict]] = []
        for i, (_initial_score, meta) in enumerate(candidates):
            scored.append((_score(meta), i, meta))

        scored.sort(key=lambda x: (-x[0], x[1]))
        return [(float(score), meta) for score, _i, meta in scored]


class CrossEncoderReranker:
    """
    Cross-encoder reranker using Sentence Transformers.

    Unlike bi-encoders (used for dense embeddings), CrossEncoders score each
    (query, passage) pair jointly, which often yields better relevance ordering
    but is heavier/slower.

    This class uses *lazy imports* so the app can run in stub-first mode even
    if `sentence_transformers` / CrossEncoder weights are not available.
    """

    def __init__(self, model_name: str):
        try:
            from sentence_transformers import CrossEncoder  # optional heavy dependency
        except ImportError as e:
            raise RuntimeError(
                "CrossEncoder reranking requires sentence-transformers. "
                "Install with `pip install -U sentence-transformers` or set "
                "RERANKING_BACKEND=stub to keep offline stub-first behavior."
            ) from e

        self.model_name = model_name
        self.model = CrossEncoder(model_name)

    def rerank(
        self, query: str, candidates: List[Tuple[float, Dict]]
    ) -> List[Tuple[float, Dict]]:
        passages = [meta.get("text", "") or "" for _score, meta in candidates]
        pairs = [(query, p) for p in passages]

        # SentenceTransformers returns array-like scores aligned with `pairs`.
        raw_scores = self.model.predict(pairs)
        scores = [float(s) for s in raw_scores]

        scored: List[Tuple[float, int, Dict]] = []
        for i, ((initial_score, meta), s) in enumerate(zip(candidates, scores)):
            scored.append((s, i, meta))

        scored.sort(key=lambda x: (-x[0], x[1]))
        return [(float(score), meta) for score, _i, meta in scored]


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
        """
        Embed and index all chunks.

        Returns:
            (new_docs_count, total_chunks_indexed)
        """
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
        """
        Retrieve k relevant chunks for `query`.

        We pass `query_text` down to the store so hybrid search can build
        the sparse keyword vector at query-time.
        """
        t0 = time.time()
        qv = self.embedder.embed(query)
        results = self.store.search(qv, k=k, query_text=query)
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
    """
    Create chunk records while preserving section context.

    For each source doc, we:
    - sentence/word-budget chunk the `text`
    - prefix each chunk with the doc's `section` header (if present)

    This increases retrieval fidelity for policy-style documents where answers
    often depend on the surrounding section heading.
    """
    out = []
    for d in docs:
        section = (d.get("section") or "").strip()
        prefix = f"{section}\n\n" if section else ""
        for ch in chunk_text(d["text"], chunk_size, overlap):
            out.append({"title": d["title"], "section": d["section"], "text": f"{prefix}{ch}"})
    return out
