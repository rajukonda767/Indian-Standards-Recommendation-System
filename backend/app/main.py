"""
main.py
=======
FastAPI main application entry point for SIH-26108 BIS AI Procurement Copilot.
"""

import sys
import logging
from contextlib import asynccontextmanager
import torch
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db import init_db_pool, close_db_pool, get_db_cursor
from app.services.embedding import embedding_service
from app.routers import recommend_router, standards_router, audit_router, audit_v2_router, bot_router, audit_pdf_router
from app.jobs.job_store import mark_stale_jobs_failed

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("bis_backend")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup sequence
    logger.info("=" * 60)
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info("=" * 60)
    
    # 1. Initialize database connection pool
    init_db_pool()

    # 1a. Mark ALL running/pending audit jobs as failed (handles server restarts mid-job)
    stale_count = mark_stale_jobs_failed()
    logger.info(f"Startup: {stale_count} stale audit job(s) marked failed.")

    # 2. Warm up local GPU embedding model (BAAI/bge-m3 on RTX 3050)
    logger.info("Pre-warming BAAI/bge-m3 embedding model on RTX 3050...")
    model = embedding_service()
    _ = model.embed_query("PVC insulated copper cable 1.5 sq mm for house wiring 1100V working voltage specification")
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    logger.info("GPU embedding model is warm and synchronized for sub-120ms inference.")

    # 3. Pre-warm persistent Groq client TLS connection
    try:
        from services.extraction import get_groq_client
        _ = get_groq_client()
        logger.info("Persistent Groq client initialized and ready.")
    except Exception as e:
        logger.warning(f"Groq warmup warning: {e}")

    yield

    # Shutdown sequence
    logger.info("Shutting down application...")
    close_db_pool()
    logger.info("Shutdown complete.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-Assisted BIS Standards Procurement Recommendation and Compliance Engine",
    lifespan=lifespan
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
from routes.recommend import router as phase1_recommend_router
app.include_router(phase1_recommend_router, prefix=settings.API_PREFIX)
app.include_router(standards_router, prefix=settings.API_PREFIX)
app.include_router(audit_router, prefix=settings.API_PREFIX)
app.include_router(audit_v2_router, prefix=settings.API_PREFIX)  # Step 1: read-only jobs endpoints
app.include_router(audit_pdf_router, prefix=settings.API_PREFIX)  # PDF export endpoint
app.include_router(bot_router, prefix=settings.API_PREFIX)

@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint reporting hardware and database connectivity status."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    gpu_info = {}
    if device == "cuda":
        gpu_info = {
            "name": torch.cuda.get_device_name(0),
            "allocated_vram_mb": round(torch.cuda.memory_allocated(0) / (1024 * 1024), 1),
            "total_vram_mb": round(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024), 1)
        }

    # Verify DB query
    db_ok = False
    standards_count = 0
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT count(*) FROM standards WHERE scope_embedding IS NOT NULL;")
            standards_count = cur.fetchone()[0]
            db_ok = True
    except Exception as e:
        logger.error(f"DB health check failed: {e}")

    return {
        "status": "healthy" if db_ok else "degraded",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "hardware": {
            "device": device,
            "gpu": gpu_info
        },
        "database": {
            "connected": db_ok,
            "embedded_standards_count": standards_count
        }
    }
