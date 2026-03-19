from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
import json
import logging
from .models import IngestResponse, AskRequest, AskResponse, MetricsResponse, Citation, Chunk
from .settings import settings
from .constants import DEFAULT_TOP_K
from .ingest import load_documents
from .rag import RAGEngine, build_chunks_from_docs

logging.basicConfig(
    level=getattr(logging, (settings.log_level or "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app")

app = FastAPI(title="AI Policy & Product Helper")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
    logger.info("ask.start k=%s query_len=%s", req.k or DEFAULT_TOP_K, len(req.query or ""))
    ctx = engine.retrieve(req.query, k=req.k or DEFAULT_TOP_K)
    logger.debug("ask.retrieved ctx=%s", len(ctx))
    answer = engine.generate(req.query, ctx)
    logger.info("ask.done ctx=%s answer_len=%s", len(ctx), len(answer or ""))
    citations = [Citation(title=c.get("title"), section=c.get("section")) for c in ctx]
    chunks = [Chunk(title=c.get("title"), section=c.get("section"), text=c.get("text")) for c in ctx]
    stats = engine.stats()
    return AskResponse(
        query=req.query,
        answer=answer,
        citations=citations,
        chunks=chunks,
        metrics={
            "retrieval_ms": stats["avg_retrieval_latency_ms"],
            "generation_ms": stats["avg_generation_latency_ms"],
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
    logger.info("ask_stream.start k=%s query_len=%s", req.k or DEFAULT_TOP_K, len(req.query or ""))
    ctx = engine.retrieve(req.query, k=req.k or DEFAULT_TOP_K)
    logger.debug("ask_stream.retrieved ctx=%s", len(ctx))
    citations = [Citation(title=c.get("title"), section=c.get("section")) for c in ctx]
    chunks = [Chunk(title=c.get("title"), section=c.get("section"), text=c.get("text")) for c in ctx]

    def event_generator():
        try:
            for token in engine.generate_stream(req.query, ctx):
                yield "event: chunk\ndata: " + json.dumps({"token": token}) + "\n\n"
        except Exception as e:
            # Ensure the client receives a useful error instead of a dropped stream.
            logger.exception("ask_stream.error err=%s", type(e).__name__)
            yield "event: chunk\ndata: " + json.dumps(
                {"token": f"\n\n[stream error: {type(e).__name__}]"}
            ) + "\n\n"
        finally:
            stats = engine.stats()
            logger.info(
                "ask_stream.done ctx=%s retrieval_ms=%s generation_ms=%s",
                len(ctx),
                stats.get("avg_retrieval_latency_ms"),
                stats.get("avg_generation_latency_ms"),
            )
            payload = {
                "citations": [c.model_dump() for c in citations],
                "chunks": [c.model_dump() for c in chunks],
                "metrics": {
                    "retrieval_ms": stats["avg_retrieval_latency_ms"],
                    "generation_ms": stats["avg_generation_latency_ms"],
                },
            }
            yield "event: done\ndata: " + json.dumps(payload) + "\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
