import json
import time
import uuid
from typing import List

from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from ..citations import select_cited_sources
from ..constants import DEFAULT_TOP_K
from ..constants import RETRIEVAL_LOG_PREVIEW_CHARS
from ..deps import get_engine, logger
from ..models import AskRequest, AskResponse, Citation, Chunk
from ..rag import RAGEngine

router = APIRouter()


@router.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest, engine: RAGEngine = Depends(get_engine)):
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
    # Log retrieved context at INFO so it's visible in default LOG_LEVEL=INFO runs.
    ctx_summaries = [
        {
            "i": i,
            "title": (c.get("title") or ""),
            "section": (c.get("section") or ""),
            "preview": ((c.get("text") or "")[:RETRIEVAL_LOG_PREVIEW_CHARS]).replace("\n", " "),
        }
        for i, c in enumerate(ctx, start=1)
    ]
    logger.info(
        "ask.ctx id=%s retrieved=%s ms=%.2f ctx=%s",
        request_id,
        len(ctx),
        retrieval_ms,
        ctx_summaries,
    )
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

    cited = select_cited_sources(answer, ctx)
    citations = [
        Citation(source_id=source_id, title=c.get("title"), section=c.get("section"))
        for source_id, c in cited
    ]
    chunks = [
        Chunk(
            source_id=source_id,
            title=c.get("title"),
            section=c.get("section"),
            text=c.get("text"),
        )
        for source_id, c in cited
    ]
    return AskResponse(
        query=req.query,
        answer=answer,
        citations=citations,
        chunks=chunks,
        metrics={
            "retrieval_ms": round(retrieval_ms, 2),
            "generation_ms": round(generation_ms, 2),
        },
    )


@router.post("/api/ask/stream")
def ask_stream(req: AskRequest, engine: RAGEngine = Depends(get_engine)):
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
    ctx_summaries = [
        {
            "i": i,
            "title": (c.get("title") or ""),
            "section": (c.get("section") or ""),
            "preview": ((c.get("text") or "")[:RETRIEVAL_LOG_PREVIEW_CHARS]).replace("\n", " "),
        }
        for i, c in enumerate(ctx, start=1)
    ]
    logger.info(
        "ask_stream.ctx id=%s retrieved=%s ms=%.2f ctx=%s",
        request_id,
        len(ctx),
        retrieval_ms,
        ctx_summaries,
    )
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

        # Debug: log what's actually in ctx before streaming
        ctx_debug = [
            {
                "title": c.get("title"),
                "section": c.get("section"),
                "text_len": len(c.get("text", "") or ""),
            }
            for c in ctx
        ]
        logger.warning("ask_stream.event_generator ctx_debug=%s", ctx_debug)

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
            cited = select_cited_sources(full_answer, ctx)
            citations = [
                Citation(source_id=source_id, title=c.get("title"), section=c.get("section"))
                for source_id, c in cited
            ]
            chunks = [
                Chunk(
                    source_id=source_id,
                    title=c.get("title"),
                    section=c.get("section"),
                    text=c.get("text"),
                )
                for source_id, c in cited
            ]
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

