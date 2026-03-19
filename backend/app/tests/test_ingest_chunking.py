from app.ingest import chunk_text


def test_chunk_text_respects_sentence_boundaries(monkeypatch):
    """Chunks should not split mid-sentence (improves embedding/retrieval quality)."""
    text = "First sentence is short. Second sentence is also short. Third is here."
    chunks = chunk_text(text, chunk_size=5, overlap=0)
    assert chunks == [
        "First sentence is short.",
        "Second sentence is also short.",
        "Third is here.",
    ]


def test_chunk_text_applies_overlap_words():
    """Overlap should carry tail words forward to reduce boundary recall loss."""
    text = "A B C D E. F G H I J. K L M N O."
    chunks = chunk_text(text, chunk_size=6, overlap=2)
    assert len(chunks) >= 2
    # The last 2 words of chunk 0 should appear at the start of chunk 1.
    tail = " ".join(chunks[0].split()[-2:])
    assert " ".join(chunks[1].split()[:2]) == tail

