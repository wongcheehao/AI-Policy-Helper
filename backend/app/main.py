from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from .settings import settings

from .endpoints.ask import router as ask_router
from .endpoints.health import router as health_router
from .endpoints.ingest import router as ingest_router
from .endpoints.metrics import router as metrics_router

logging.basicConfig(
    level=getattr(logging, (settings.log_level or "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
def create_app() -> FastAPI:
    """
    FastAPI application factory.

    Keeping app construction in a function makes the HTTP layer easier to test
    and keeps `main.py` focused on wiring (not business logic).
    """
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

    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(ingest_router)
    app.include_router(ask_router)

    return app


app = create_app()
