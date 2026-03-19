"""
Project-wide constants.

Keep magic values out of core logic by defining stable defaults here.
If a value should be configurable at runtime, prefer an env var in `settings.py`
instead of hardcoding it.
"""

# Embeddings / retrieval
LOCAL_EMBEDDING_MODEL_NAME = "local-384"
DEFAULT_SENTENCE_TRANSFORMER_MODEL = "all-MiniLM-L6-v2"
DEFAULT_EMBED_DIM = 384
DEFAULT_TOP_K = 4

# Hybrid search (Qdrant dense + sparse)
DEFAULT_HYBRID_SEARCH_ENABLED = True
QDRANT_DENSE_VECTOR_NAME = "dense"
QDRANT_SPARSE_VECTOR_NAME = "sparse"
SPARSE_HASH_DIM = 65536  # hashed vocabulary size for sparse encoding

# Chunking (word-based heuristic; tuned for SBERT-friendly context sizes)
#
# Why ~256 words?
# - Sentence-Transformers / transformer encoders have a fixed max input length
#   (`model.max_seq_length`); longer inputs are truncated. Keeping chunks in the
#   few-hundred-word range reduces truncation risk while staying semantically
#   coherent for retrieval.
# - SBERT docs highlight that longer sequences are expensive (quadratic cost)
#   and are truncated beyond `max_seq_length`, so splitting is the intended way
#   to handle long documents.
#
# References:
# - SentenceTransformer `max_seq_length` (inputs longer are truncated):
#   https://www.sbert.net/docs/package_reference/sentence_transformer/SentenceTransformer
# - Input sequence length notes + truncation guidance:
#   https://www.sbert.net/examples/sentence_transformer/applications/computing-embeddings/README.html
DEFAULT_CHUNK_SIZE_WORDS = 256
# Why 40-word overlap?
# - Overlap reduces “boundary loss” where an answer spans the end/start of two
#   chunks, improving recall without ballooning index size.
DEFAULT_CHUNK_OVERLAP_WORDS = 40

# Sentence splitting heuristic used by `ingest.chunk_text`.
SENTENCE_SPLIT_PATTERN = r"(?<=[.!?])\s+"

# Generation / prompting
DEFAULT_CONTEXT_PREVIEW_CHARS = 600

# Providers / infra
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
QDRANT_TIMEOUT_S = 10.0

# ---- Generation / prompting (RAG grounding) ----
#
# PromptingGuide best practice: make the generation step explicitly grounded in
# retrieved sources, and require a clear citation format to improve faithfulness.
#
# Note: we keep the stub answer and OpenRouter answer aligned by using the same
# citation bracket format: `[Source Title -- Section]`.

# Inline citation format expected in the model's answer.
CITATION_BRACKET_FORMAT = "[{title} -- {section}]"

# System prompt that instructs the model to answer only from sources and to use
# the above citation format.
SYSTEM_PROMPT = """You are a company policy assistant.

Answer ONLY from the provided sources.
When you use information from a source, include an inline citation in the form
[{Source Title} -- {Section}].

If the sources do not contain the answer, respond exactly with:
I don't have enough information to answer that.

Be concise and factual. Do not invent or infer details not present in the sources.
"""

