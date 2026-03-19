from fastapi import APIRouter, Depends

from ..deps import get_engine
from ..models import MetricsResponse
from ..rag import RAGEngine

router = APIRouter()


@router.get("/api/metrics", response_model=MetricsResponse)
def metrics(engine: RAGEngine = Depends(get_engine)):
    s = engine.stats()
    return MetricsResponse(**s)

