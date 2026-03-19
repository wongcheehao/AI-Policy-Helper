"""
Dependency wiring for the FastAPI layer.

We keep singletons (logger, RAG engine) here so endpoint modules remain focused
on request/response handling.
"""

from __future__ import annotations

import logging

from .rag import RAGEngine

logger = logging.getLogger("app")

_engine: RAGEngine | None = None


def get_engine() -> RAGEngine:
    global _engine
    if _engine is None:
        _engine = RAGEngine()
    return _engine

