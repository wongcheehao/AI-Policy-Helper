from fastapi import APIRouter, Depends

from ..deps import get_engine, logger
from ..ingest import load_documents
from ..models import IngestResponse
from ..rag import RAGEngine, build_chunks_from_docs
from ..settings import settings

router = APIRouter()


@router.post("/api/ingest", response_model=IngestResponse)
def ingest(engine: RAGEngine = Depends(get_engine)):
    logger.info("ingest.start data_dir=%s", settings.data_dir)
    docs = load_documents(settings.data_dir)
    chunks = build_chunks_from_docs(docs, settings.chunk_size, settings.chunk_overlap)
    new_docs, new_chunks = engine.ingest_chunks(chunks)
    logger.info("ingest.done new_docs=%s new_chunks=%s", new_docs, new_chunks)
    return IngestResponse(indexed_docs=new_docs, indexed_chunks=new_chunks)

