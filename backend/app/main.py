from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
import json
import logging
import time
import uuid
from typing import List
from .models import IngestResponse, AskRequest, AskResponse, MetricsResponse, Citation, Chunk
from .settings import settings
from .constants import DEFAULT_TOP_K
from .ingest import load_documents
from .rag import RAGEngine, build_chunks_from_docs
from .citations import filter_ctx_by_citations

logging.basicConfig(
    level=getattr(logging, (settings.log_level or "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app")

app = FastAPI(title="AI Policy & Product Helper")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = RAGEngine()


@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/metrics", response_model=MetricsResponse)
def metrics():
    s = engine.stats()
    return MetricsResponse(**s)

@app.post("/api/ingest", response_model=IngestResponse)
def ingest():
    logger.info("ingest.start data_dir=%s", settings.data_dir)
    docs = load_documents(settings.data_dir)
    chunks = build_chunks_from_docs(docs, settings.chunk_size, settings.chunk_overlap)
    new_docs, new_chunks = engine.ingest_chunks(chunks)
    logger.info("ingest.done new_docs=%s new_chunks=%s", new_docs, new_chunks)
    return IngestResponse(indexed_docs=new_docs, indexed_chunks=new_chunks)

@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest):
    request_id = uuid.uuid4().hex[:10]
    logger.info(
        "ask.start id=%s k=%s query_len=%s",
        request_id,
        req.k or DEFAULT_TOP_K,
        len(req.query or ""),
    )
    t_retrieval0 = time.time()
    ctx = engine.retrieve(req.query, k=req.k or DEFAULT_TOP_K)
    retrieval_ms = (time.time() - t_retrieval0) * 1000.0
    logger.debug(
        "ask.retrieved id=%s ctx=%s ms=%.2f sources=%s",
        request_id,
        len(ctx),
        retrieval_ms,
        [(c.get("title"), c.get("section")) for c in ctx],
    )
    t_gen0 = time.time()
    answer = engine.generate(req.query, ctx)
    generation_ms = (time.time() - t_gen0) * 1000.0
    logger.info(
        "ask.done id=%s ctx=%s answer_len=%s retrieval_ms=%.2f generation_ms=%.2f",
        request_id,
        len(ctx),
        len(answer or ""),
        retrieval_ms,
        generation_ms,
    )
    cited_ctx = filter_ctx_by_citations(answer, ctx)
    citations = [Citation(title=c.get("title"), section=c.get("section")) for c in cited_ctx]
    chunks = [Chunk(title=c.get("title"), section=c.get("section"), text=c.get("text")) for c in cited_ctx]
    return AskResponse(
        query=req.query,
        answer=answer,
        citations=citations,
        chunks=chunks,
        metrics={
            "retrieval_ms": round(retrieval_ms, 2),
            "generation_ms": round(generation_ms, 2),
        }
    )


@app.post("/api/ask/stream")
def ask_stream(req: AskRequest):
    """
    Server-Sent Events (SSE) endpoint.

    Emits:
    - event: chunk  (data: {"token": "..."}) repeatedly
    - event: done   (data: {"citations": [...], "chunks": [...], "metrics": {...}})
    """
    request_id = uuid.uuid4().hex[:10]
    logger.info(
        "ask_stream.start id=%s k=%s query_len=%s",
        request_id,
        req.k or DEFAULT_TOP_K,
        len(req.query or ""),
    )
    t_retrieval0 = time.time()
    ctx = engine.retrieve(req.query, k=req.k or DEFAULT_TOP_K)
    retrieval_ms = (time.time() - t_retrieval0) * 1000.0
    logger.debug(
        "ask_stream.retrieved id=%s ctx=%s ms=%.2f sources=%s",
        request_id,
        len(ctx),
        retrieval_ms,
        [(c.get("title"), c.get("section")) for c in ctx],
    )
    def event_generator():
        t_gen0 = time.time()
        answer_parts: List[str] = []
        try:
            for token in engine.generate_stream(req.query, ctx):
                answer_parts.append(token)
                yield "event: chunk\ndata: " + json.dumps({"token": token}) + "\n\n"
        except Exception as e:
            # Ensure the client receives a useful error instead of a dropped stream.
            logger.exception("ask_stream.error err=%s", type(e).__name__)
            yield "event: chunk\ndata: " + json.dumps(
                {"token": f"\n\n[stream error: {type(e).__name__}]"}
            ) + "\n\n"
        finally:
            full_answer = "".join(answer_parts)
            generation_ms = (time.time() - t_gen0) * 1000.0
            logger.info(
                "ask_stream.done id=%s ctx=%s retrieval_ms=%.2f generation_ms=%.2f",
                request_id,
                len(ctx),
                retrieval_ms,
                generation_ms,
            )
            cited_ctx = filter_ctx_by_citations(full_answer, ctx)
            citations = [Citation(title=c.get("title"), section=c.get("section")) for c in cited_ctx]
            chunks = [Chunk(title=c.get("title"), section=c.get("section"), text=c.get("text")) for c in cited_ctx]
            payload = {
                "citations": [c.model_dump() for c in citations],
                "chunks": [c.model_dump() for c in chunks],
                "metrics": {
                    "retrieval_ms": round(retrieval_ms, 2),
                    "generation_ms": round(generation_ms, 2),
                },
            }
            yield "event: done\ndata: " + json.dumps(payload) + "\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
