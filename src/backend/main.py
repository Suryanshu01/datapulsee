"""
DataPulse - Talk to Your Data: Seamless Self-Service Intelligence

FastAPI application entry point. This file is intentionally thin:
it creates the app, registers middleware, includes routers, and exposes
a health endpoint. All business logic lives in routes/, services/, and utils/.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import semantic, upload
from routes import query as query_router
from routes import dashboard as dashboard_router
from utils.duckdb_manager import session_count
from utils.cache import cache_stats

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log startup confirmation so it's easy to tell the server is healthy."""
    groq_key_set = bool(os.getenv("GROQ_API_KEY"))
    logger.info("DataPulse starting. GROQ_API_KEY present: %s", groq_key_set)
    if not groq_key_set:
        logger.warning(
            "GROQ_API_KEY is not set - AI features will fail. "
            "Copy .env.example to .env and add your key."
        )
    yield
    logger.info("DataPulse shutting down. Sessions active: %d", session_count())


app = FastAPI(
    title="DataPulse",
    description="Talk to your data. Get answers you trust.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(query_router.router)
app.include_router(semantic.router)
app.include_router(dashboard_router.router)


@app.get("/api/health")
async def health() -> dict:
    """Health check endpoint."""
    return {
        "status": "ok",
        "sessions": session_count(),
        "cache": cache_stats(),
        "groq_key_set": bool(os.getenv("GROQ_API_KEY")),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
