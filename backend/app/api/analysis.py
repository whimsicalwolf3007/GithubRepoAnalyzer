"""
Analysis API — Trigger and monitor repository analysis.
"""
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, AsyncSessionLocal
from app.models import Repository, UploadBatch, RepoStatus
from app.schemas import AnalysisStatusResponse, AnalyzeRequest
from app.services.pipeline import analyze_single_repository, analyze_batch
from app.engines.input_processor import parse_text_urls

logger = logging.getLogger(__name__)
router = APIRouter()


async def _run_analysis_bg(repo_id: UUID):
    """Background task to run analysis."""
    async with AsyncSessionLocal() as db:
        try:
            result = await analyze_single_repository(db, repo_id)
            logger.info(f"Background analysis complete: {result}")
        except Exception as e:
            logger.error(f"Background analysis failed: {e}")


async def _run_batch_analysis_bg(batch_id: UUID):
    """Background task to run batch analysis."""
    async with AsyncSessionLocal() as db:
        try:
            result = await analyze_batch(db, batch_id)
            logger.info(f"Background batch analysis complete: {result}")
        except Exception as e:
            logger.error(f"Background batch analysis failed: {e}")


@router.post("/analyze/{repo_id}", response_model=AnalysisStatusResponse)
async def trigger_analysis(
    repo_id: UUID,
    background_tasks: BackgroundTasks,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Trigger analysis for a single repository. Runs in the background."""
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    if not force and repo.status in (RepoStatus.SCRAPING, RepoStatus.ANALYZING, RepoStatus.BUILDING):
        raise HTTPException(status_code=409, detail="Analysis already in progress")

    # Reset status
    repo.status = RepoStatus.QUEUED
    await db.commit()

    # Run in background
    background_tasks.add_task(_run_analysis_bg, repo_id)

    return AnalysisStatusResponse(
        repo_id=repo.id,
        status=RepoStatus.QUEUED,
        message=f"Analysis queued for {repo.owner}/{repo.name}",
    )


@router.post("/analyze/batch/{batch_id}")
async def trigger_batch_analysis(
    batch_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger analysis for all repositories in a batch."""
    result = await db.execute(select(UploadBatch).where(UploadBatch.id == batch_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    background_tasks.add_task(_run_batch_analysis_bg, batch_id)

    return {
        "batch_id": str(batch_id),
        "message": f"Batch analysis started for {batch.total_repos} repositories",
    }


@router.post("/analyze/url")
async def analyze_url(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Quick analyze: submit a single GitHub URL for immediate analysis."""
    if not request.url:
        raise HTTPException(status_code=400, detail="URL is required")

    repos_data = parse_text_urls(request.url)
    if not repos_data:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")

    repo_data = repos_data[0]

    # Check if already exists
    existing = await db.execute(
        select(Repository).where(
            Repository.owner == repo_data["owner"],
            Repository.name == repo_data["name"],
        )
    )
    repo = existing.scalar_one_or_none()

    if not repo:
        repo = Repository(
            url=repo_data["url"],
            owner=repo_data["owner"],
            name=repo_data["name"],
        )
        db.add(repo)
        await db.commit()
        await db.refresh(repo)

    background_tasks.add_task(_run_analysis_bg, repo.id)

    return {
        "repo_id": str(repo.id),
        "message": f"Analysis started for {repo.owner}/{repo.name}",
    }


@router.get("/analyze/{repo_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    repo_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the current analysis status for a repository."""
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    status_messages = {
        RepoStatus.QUEUED: "Waiting in queue",
        RepoStatus.SCRAPING: "Scraping GitHub data",
        RepoStatus.ANALYZING: "Analyzing tech stack",
        RepoStatus.BUILDING: "Running build simulation",
        RepoStatus.COMPLETED: "Analysis complete",
        RepoStatus.FAILED: f"Analysis failed: {repo.error_message or 'Unknown error'}",
    }

    return AnalysisStatusResponse(
        repo_id=repo.id,
        status=repo.status,
        message=status_messages.get(repo.status, "Unknown status"),
    )
