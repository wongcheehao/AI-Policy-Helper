from pydantic import BaseModel
import os

from .constants import (
    DEFAULT_CHUNK_OVERLAP_WORDS,
    DEFAULT_CHUNK_SIZE_WORDS,
    DEFAULT_HYBRID_SEARCH_ENABLED,
    DEFAULT_SENTENCE_TRANSFORMER_MODEL,
)

class Settings(BaseModel):
    embedding_model: str = os.getenv("EMBEDDING_MODEL", DEFAULT_SENTENCE_TRANSFORMER_MODEL)
    llm_provider: str = os.getenv("LLM_PROVIDER", "stub")  # stub | openrouter | ollama
    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    llm_model: str = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    qdrant_url: str = os.getenv("QDRANT_URL", "http://qdrant:6333")
    vector_store: str = os.getenv("VECTOR_STORE", "qdrant")  # qdrant | memory
    collection_name: str = os.getenv("COLLECTION_NAME", "policy_helper")
    hybrid_search_enabled: bool = os.getenv(
        "HYBRID_SEARCH_ENABLED", "true" if DEFAULT_HYBRID_SEARCH_ENABLED else "false"
    ).lower() in {"1", "true", "yes", "y", "on"}
    chunk_size: int = int(os.getenv("CHUNK_SIZE", str(DEFAULT_CHUNK_SIZE_WORDS)))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", str(DEFAULT_CHUNK_OVERLAP_WORDS)))
    data_dir: str = os.getenv("DATA_DIR", "/app/data")

settings = Settings()
