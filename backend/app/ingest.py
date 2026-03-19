import hashlib
import os
import re
from typing import Dict, List, Tuple

from .constants import SENTENCE_SPLIT_PATTERN

def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def _md_sections(text: str) -> List[Tuple[str, str]]:
    # Very simple section splitter by Markdown headings
    parts = re.split(r"\n(?=#+\s)", text)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        lines = p.splitlines()
        title = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("#") else "Body"
        out.append((title, p))
    return out or [("Body", text)]

_SENTENCE_SPLIT_RE = re.compile(SENTENCE_SPLIT_PATTERN)


def _split_sentences(text: str) -> List[str]:
    """Split text into sentence-like segments using a lightweight heuristic."""
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(normalized) if s.strip()]


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """
    Chunk text using sentence boundaries while approximately respecting a word budget.

    The parameters are treated as a **word-count heuristic**:
    - `chunk_size`: maximum words per chunk target
    - `overlap`: overlap in words between consecutive chunks
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be < chunk_size")

    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks: List[str] = []
    current: List[str] = []
    current_words = 0

    def _flush():
        nonlocal current, current_words
        if not current:
            return
        chunks.append(" ".join(current).strip())
        if overlap == 0:
            current = []
            current_words = 0
            return

        # Keep the last `overlap` words as seed for the next chunk.
        words = " ".join(current).split()
        tail = words[-overlap:] if len(words) >= overlap else words
        current = [" ".join(tail)] if tail else []
        current_words = len(tail)

    for s in sentences:
        s_words = len(s.split())
        if s_words > chunk_size and not current:
            # Extremely long "sentence": hard-split by word budget.
            words = s.split()
            i = 0
            while i < len(words):
                piece = " ".join(words[i : i + chunk_size])
                chunks.append(piece)
                if i + chunk_size >= len(words):
                    break
                i += chunk_size - overlap if overlap > 0 else chunk_size
            continue

        if current_words + s_words > chunk_size and current:
            _flush()

        current.append(s)
        current_words += s_words

    _flush()
    return [c for c in chunks if c]

def load_documents(data_dir: str) -> List[Dict]:
    docs = []
    for fname in sorted(os.listdir(data_dir)):
        if not fname.lower().endswith((".md", ".txt")):
            continue
        path = os.path.join(data_dir, fname)
        text = _read_text_file(path)
        for section, body in _md_sections(text):
            docs.append({
                "title": fname,
                "section": section,
                "text": body
            })
    return docs

def doc_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
