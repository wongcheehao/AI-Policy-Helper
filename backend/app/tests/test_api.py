from app.constants import CITATION_BRACKET_FORMAT
from app.settings import settings

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
