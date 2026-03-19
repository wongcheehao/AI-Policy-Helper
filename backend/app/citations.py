"""
Citation extraction and source filtering.

Separation of concerns:
- `main.py` should focus on HTTP concerns.
- Citation parsing/filtering is pure business logic and is unit-testable.
"""

from __future__ import annotations

import re
from typing import List, Tuple

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
    import logging
    logger = logging.getLogger("app.citations")

    normalized = (answer or "").strip().replace("\n", " ")
    normalized = " ".join(normalized.split())
    if normalized == NO_INFO_ANSWER:
        return []

    cited_ids = extract_cited_source_ids(answer or "")

    # Debug: log context order and cited IDs
    ctx_debug = [(i, c.get("title"), c.get("section")) for i, c in enumerate(ctx)]
    logger.warning(f"filter_ctx_by_citations ctx_order={ctx_debug} cited_ids={cited_ids}")

    if not cited_ids:
        return []

    selected: List[dict] = []
    for n in cited_ids:
        i = n - 1
        if 0 <= i < len(ctx):
            selected.append(ctx[i])
            logger.warning(f"filter_ctx_by_citations citation[^{n}] -> ctx[{i}] = {ctx[i].get('title')}")
    return selected


def select_cited_sources(answer: str, ctx: List[dict]) -> List[Tuple[int, dict]]:
    """
    Return cited sources as `(source_id, ctx_item)` pairs.

    `source_id` is the original 1-based marker used in the model output (`[^n]`).
    Preserving this value prevents frontend re-numbering mismatches.
    """
    normalized = (answer or "").strip().replace("\n", " ")
    normalized = " ".join(normalized.split())
    if normalized == NO_INFO_ANSWER:
        return []

    cited_ids = extract_cited_source_ids(answer or "")
    selected: List[Tuple[int, dict]] = []
    for n in cited_ids:
        i = n - 1
        if 0 <= i < len(ctx):
            selected.append((n, ctx[i]))
    return selected

