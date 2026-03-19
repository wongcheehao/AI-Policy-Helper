"""
Citation extraction and source filtering.

Separation of concerns:
- `main.py` should focus on HTTP concerns.
- Citation parsing/filtering is pure business logic and is unit-testable.
"""

from __future__ import annotations

import re
from typing import List

from .constants import CITATION_MARKER_REGEX, NO_INFO_ANSWER

_CITATION_MARKER_RE = re.compile(CITATION_MARKER_REGEX)


def extract_cited_source_ids(answer: str) -> List[int]:
    """
    Extract 1-based numeric citation markers (e.g. [^1]) from an answer.

    Returns unique ids in order of first appearance.
    """
    if not answer:
        return []
    seen = set()
    out: List[int] = []
    for m in _CITATION_MARKER_RE.finditer(answer):
        try:
            n = int(m.group(1))
        except Exception:
            continue
        if n <= 0 or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def filter_ctx_by_citations(answer: str, ctx: List[dict]) -> List[dict]:
    """
    Make the backend authoritative about citations.

    Rules:
    - If the model refuses with the exact refusal string, return no sources.
    - Otherwise, return only ctx entries that were actually cited via [^n].

    This avoids a common RAG UX bug where the UI shows "retrieved" sources even
    if the model didn't actually use them in the final answer.
    """
    normalized = (answer or "").strip().replace("\n", " ")
    normalized = " ".join(normalized.split())
    if normalized == NO_INFO_ANSWER:
        return []

    cited_ids = extract_cited_source_ids(answer or "")
    if not cited_ids:
        return []

    selected: List[dict] = []
    for n in cited_ids:
        i = n - 1
        if 0 <= i < len(ctx):
            selected.append(ctx[i])
    return selected

