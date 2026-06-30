"""
FastAPI Application Entry Point — AutoDev Intelligence API.
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.database import init_db
from app.api import upload, repositories, analysis, dashboard, reports

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    logger.info("🚀 Starting AutoDev Intelligence API")
    await init_db()
    logger.info("✅ Database initialized")

    # Create directories
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.REPORTS_DIR).mkdir(parents=True, exist_ok=True)
    logger.info("✅ Directories created")

    yield

    # Shutdown
    logger.info("🛑 Shutting down AutoDev Intelligence API")


# Create FastAPI app
app = FastAPI(
    title="AutoDev Intelligence API",
    description="GitHub Repository Analyzer & Build Feasibility Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(repositories.router, prefix="/api", tags=["Repositories"])
app.include_router(analysis.router, prefix="/api", tags=["Analysis"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(reports.router, prefix="/api", tags=["Reports"])


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "AutoDev Intelligence API",
        "version": "1.0.0",
    }
