"""FastAPI application — FinPilot HomeLoan: explainable underwriting in minutes.

Run: ``uvicorn app.main:app --reload --port 8000`` (from ``backend/``).

Environment:
  ALLOWED_ORIGINS   comma-separated CORS origins (default ``*``)
  DEMO_MODE         ``1`` (default) preloads the synthetic personas and enables ``/api/demo/reset``
  PRELOAD_PERSONAS  ``0`` to skip the startup preload even in demo mode
  DATA_DIR          persistence root (default ``backend/.data``)
  OLLAMA_HOST / OLLAMA_MODEL / GEMINI_API_KEY / GEMINI_MODEL / COPILOT_LLM  optional LLM for the copilot
"""
from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import demo_mode, router
from app.store import get_store

log = logging.getLogger("finpilot")

TAGS = [
    {"name": "system", "description": "Health and status"},
    {"name": "policy", "description": "Versioned machine-readable credit policy"},
    {"name": "personas", "description": "Synthetic demo applicants and their documents"},
    {"name": "cases", "description": "Underwrite applications and fetch case files"},
    {"name": "underwriter", "description": "Human-in-the-loop overrides"},
    {"name": "copilot", "description": "Grounded Q&A over a case (cites rule IDs)"},
    {"name": "reports", "description": "Credit memo, sanction letter / KFS, rejection letter"},
    {"name": "portfolio", "description": "Portfolio-level metrics"},
    {"name": "model", "description": "Risk model card"},
    {"name": "demo", "description": "Demo utilities"},
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    st = get_store()
    n = st.load_from_disk()
    log.info("loaded %d persisted case(s) from %s", n, st.root)
    if demo_mode() and os.getenv("PRELOAD_PERSONAS", "1") != "0":
        st.start_preload()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="FinPilot HomeLoan API",
        version="1.0.0",
        description="Explainable, policy-driven mortgage underwriting (Home Loan & LAP) with an "
                    "agentic Underwriting Copilot. Synthetic data; decision support for underwriters.",
        openapi_tags=TAGS,
        lifespan=lifespan,
    )
    origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()] or ["*"]
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_credentials=origins != ["*"],
        allow_methods=["*"], allow_headers=["*"],
    )
    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"name": "FinPilot HomeLoan API", "docs": "/docs", "health": "/api/health"}

    return app


app = create_app()
