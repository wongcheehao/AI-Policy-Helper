## Chunking design (sentence-aware, word-budgeted)

### Goal

Produce chunks that are:
- **Good embedding inputs** (not too long, semantically coherent)
- **Retrieval-friendly** (avoid splitting facts mid-sentence)
- **Deterministic** (stable for tests/eval)

### Inputs

- **Text**: section-level Markdown body from `load_documents()`
- **Parameters** (word-count heuristic):
  - `chunk_size` (default `256`)
  - `overlap` (default `40`)

Defaults are defined in `backend/app/constants.py` and surfaced via env (`CHUNK_SIZE`, `CHUNK_OVERLAP`).

### Algorithm (in `backend/app/ingest.py`)

1. **Normalize whitespace**: collapse repeated whitespace to single spaces.
2. **Split into sentences** using a lightweight regex heuristic:
   - Pattern: `SENTENCE_SPLIT_PATTERN = r"(?<=[.!?])\s+"`
3. **Accumulate sentences** into a chunk until adding the next sentence would exceed `chunk_size` words.
4. **Flush chunk**:
   - Emit the joined sentences as one chunk.
   - Seed the next chunk with the **last `overlap` words** from the previous chunk (boundary recall).
5. **Long-sentence fallback**:
   - If a single “sentence” is longer than `chunk_size` and the current chunk is empty, hard-split by word budget with overlap.

### Trade-offs

- **Pros**:
  - Better semantic cohesion than naive fixed-token splitting.
  - Reduced truncation risk vs. embedding very long sections.
  - Overlap improves recall for answers spanning chunk boundaries.
- **Cons**:
  - Regex sentence splitting is heuristic (not perfect for abbreviations, non-English, bullet lists).
  - “Words” are a proxy for tokens; exact token budgets require a tokenizer (optional future upgrade).

### Future upgrades (if needed)

- Tokenizer-based chunking (true token budgets per model)
- Markdown-aware chunking (bullets, tables)
- Add “section heading prefix” into each chunk’s text (already in plan; implement if retrieval needs more context)

