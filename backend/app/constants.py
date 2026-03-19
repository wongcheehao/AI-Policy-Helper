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

# Generation / prompting
DEFAULT_CONTEXT_PREVIEW_CHARS = 600

# Providers / infra
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
QDRANT_TIMEOUT_S = 10.0

