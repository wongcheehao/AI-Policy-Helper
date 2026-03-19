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
RETRIEVAL_CANDIDATE_MULTIPLIER = 2
RETRIEVAL_CANDIDATE_MIN = 10
HYBRID_RETRIEVAL_CANDIDATE_MULTIPLIER = 4
HYBRID_RETRIEVAL_CANDIDATE_MIN = 20

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
OPENROUTER_TEMPERATURE = 0.1
STUB_STREAM_CHUNK_SIZE = 25

# Logging
# Keep retrieved chunk previews short to avoid dumping full docs into logs.
RETRIEVAL_LOG_PREVIEW_CHARS = 160

# Providers / infra
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
QDRANT_TIMEOUT_S = 10.0
DEFAULT_HF_HOME = "/app/.cache/huggingface"
DEFAULT_SENTENCE_TRANSFORMERS_HOME = "/app/.cache/sentence_transformers"

# Reranking
RERANK_EMPTY_TEXT_PENALTY = -999.0

# ---- Generation / prompting (RAG grounding) ----
#
# PromptingGuide best practice: make the generation step explicitly grounded in
# retrieved sources, and require a clear citation format to improve faithfulness.
#
# Note: we keep the stub answer and OpenRouter answer aligned by using the same
# citation bracket format: `[Source Title -- Section]`.

# Inline citation format expected in the model's answer.
# We use a numeric marker so the UI can render clickable superscripts.
SOURCE_CITATION_MARKER = "[^{n}]"

# Exact refusal string (kept in one place so prompt + server behavior stay aligned).
NO_INFO_ANSWER = "I don't have enough information to answer that."

# Regex for extracting numeric citation markers like `[^1]` from model output.
CITATION_MARKER_REGEX = r"\[\^(\d+)\]"

# System prompt that instructs the model to answer only from sources and to use
# the above citation format.
# Enhanced with Chain-of-Thought reasoning for conditional logic and ambiguity handling.
SYSTEM_PROMPT = """You are a company policy assistant.

Answer customer questions based ONLY on the provided policy sources.

REASONING STEPS:
1. Check if the question has AMBIGUOUS TERMS (e.g., "damaged" could mean "defective" or "misuse")
2. Check if the answer DEPENDS ON CONDITIONS not stated in the question
3. Review ALL relevant policy paths in the sources

RESPONSE FORMAT:

**If answer is CONDITIONAL** (depends on unstated information):
- Explain what the answer depends on
- Use clear IF-THEN structure
- Cite each condition: "IF [scenario A], THEN [outcome A] [^1]. IF [scenario B], THEN [outcome B] [^2]."
- Example: "The answer depends on the type of damage. IF the blender has a manufacturing defect, THEN it can be returned within 30 days [^1]. IF the damage is from misuse (e.g., dropping it), THEN it is NOT covered [^2]."

**If answer is STRAIGHTFORWARD**:
- Answer directly with citations [^1], [^2]
- Be concise and factual

**If sources lack the answer**:
- Respond exactly: "I don't have enough information to answer that."
- NO citations

CITATION RULES:
- Every factual claim needs citation markers [^1], [^2], etc.
- Match citation numbers to source numbers in Sources list
- Do not invent information not in sources

Be helpful by acknowledging when policies have conditional logic rather than forcing a single answer."""

