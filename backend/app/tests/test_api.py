from app.constants import CITATION_BRACKET_FORMAT
from app.settings import settings
import json

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_ingest_and_ask(client):
    r = client.post("/api/ingest")
    assert r.status_code == 200
    # Ask a deterministic question
    r2 = client.post("/api/ask", json={"query":"What is the refund window for small appliances?"})
    assert r2.status_code == 200
    data = r2.json()
    assert "citations" in data and len(data["citations"]) > 0
    assert "answer" in data and isinstance(data["answer"], str)

    # Stub mode must emit a citation-shaped "Sources" section so the UI can display
    # grounding consistently even without a real model.
    if settings.llm_provider == "stub":
        assert "Sources:" in data["answer"]
        first = data["citations"][0]
        title = first.get("title")
        section = first.get("section") or "Section"
        expected_ref = CITATION_BRACKET_FORMAT.format(title=title, section=section)
        assert expected_ref in data["answer"]


def test_ask_stream_sse(client):
    client.post("/api/ingest")
    with client.stream(
        "POST",
        "/api/ask/stream",
        json={"query": "What is the refund window for small appliances?"},
    ) as resp:
        assert resp.status_code == 200

        current_event = None
        events = []
        for line in resp.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="replace")
            if line.startswith("event:"):
                current_event = line.split("event:", 1)[1].strip()
            elif line.startswith("data:"):
                payload = json.loads(line.split("data:", 1)[1].strip())
                events.append((current_event, payload))

        chunk_events = [p for ev, p in events if ev == "chunk" and isinstance(p, dict)]
        assert len(chunk_events) > 0

        done_events = [p for ev, p in events if ev == "done" and isinstance(p, dict)]
        assert len(done_events) == 1
        done = done_events[0]
        assert "citations" in done and len(done["citations"]) > 0
        assert "chunks" in done
        assert "metrics" in done
