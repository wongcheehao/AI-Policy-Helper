## Hybrid search design (dense + sparse fusion with RRF)

### Goal

Improve retrieval for policy-like documents by combining:
- **Dense vectors**: semantic similarity (handles paraphrases)
- **Sparse vectors**: exact token matching (handles keywords like “bulky”, SKUs, numbers)

### Why this fits our dataset

The `data/` docs contain short headings and bullet points with key terms (e.g., “bulky items”, “surcharge”, “SKU”, “12–24 months”). Sparse signals help ensure we don’t miss exact-match cues, while dense embeddings handle paraphrased queries.

This aligns with “Advanced RAG” guidance that retrieval quality can be improved via **mixed / hybrid retrieval** and by choosing chunking/indexing strategies appropriate to the content. See:
- PromptingGuide RAG retrieval notes: https://www.promptingguide.ai/research/rag.en#retrieval

### Qdrant approach

Use Qdrant hybrid queries with Reciprocal Rank Fusion (RRF):
- Store **named dense** vector: `"dense"`
- Store **named sparse** vector: `"sparse"`
- Query using `prefetch=[dense_query, sparse_query]` + `FusionQuery(fusion=RRF)`

Reference examples:
- Qdrant hybrid queries + RRF: https://qdrant.tech/documentation/concepts/hybrid-queries

### Sparse encoding approach (no external model)

To keep the project simple and offline-friendly, sparse vectors are produced via:
- tokenize → hash tokens into a fixed index space → use term counts as values

This is not full BM25, but it captures useful exact-token signals without adding heavy dependencies.

### Config knobs

- `HYBRID_SEARCH_ENABLED` (default: `true` for Qdrant)
- `SPARSE_HASH_DIM` (hashed vocab size; constant)

