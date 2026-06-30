"""
Upload API — Excel file upload and single URL submission.
"""
import shutil
import logging
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.config import settings
from app.models import UploadBatch, Repository, BatchStatus
from app.schemas import UploadResponse, BatchStatusResponse, AnalyzeRequest
from app.engines.input_processor import parse_excel_file, parse_text_urls

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_excel(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload an Excel file containing GitHub repository links.
    Parses the file, extracts valid GitHub URLs, and creates a batch for processing.
    """
    # Validate file type
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx and .xls files are supported")

    # Save uploaded file
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename

    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # Parse Excel file
    try:
        repos_data = parse_excel_file(str(file_path))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not repos_data:
        raise HTTPException(status_code=400, detail="No valid GitHub URLs found in the Excel file")

    # Create batch
    batch = UploadBatch(
        filename=file.filename,
        total_repos=len(repos_data),
        status=BatchStatus.PENDING,
    )
    db.add(batch)
    await db.flush()

    # Create repository records
    repo_urls = []
    for repo_data in repos_data:
        repo = Repository(
            batch_id=batch.id,
            url=repo_data["url"],
            owner=repo_data["owner"],
            name=repo_data["name"],
        )
        db.add(repo)
        repo_urls.append(repo_data["url"])

    await db.commit()

    logger.info(f"Uploaded {file.filename}: {len(repos_data)} repositories in batch {batch.id}")

    return UploadResponse(
        batch_id=batch.id,
        filename=file.filename,
        total_repos=len(repos_data),
        repositories=repo_urls,
        message=f"Successfully parsed {len(repos_data)} GitHub repositories",
    )


@router.post("/upload/url", response_model=UploadResponse)
async def upload_single_url(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a single GitHub URL or multiple URLs (comma/newline separated) for analysis."""
    if not request.url:
        raise HTTPException(status_code=400, detail="URL is required")

    repos_data = parse_text_urls(request.url)
    if not repos_data:
        raise HTTPException(status_code=400, detail="No valid GitHub URLs found")

    # Create batch
    batch = UploadBatch(
        filename="manual_input",
        total_repos=len(repos_data),
        status=BatchStatus.PENDING,
    )
    db.add(batch)
    await db.flush()

    repo_urls = []
    for repo_data in repos_data:
        repo = Repository(
            batch_id=batch.id,
            url=repo_data["url"],
            owner=repo_data["owner"],
            name=repo_data["name"],
        )
        db.add(repo)
        repo_urls.append(repo_data["url"])

    await db.commit()

    return UploadResponse(
        batch_id=batch.id,
        filename="manual_input",
        total_repos=len(repos_data),
        repositories=repo_urls,
        message=f"Successfully queued {len(repos_data)} repositories for analysis",
    )


@router.get("/upload/{batch_id}/status", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the processing status of a batch upload."""
    result = await db.execute(select(UploadBatch).where(UploadBatch.id == batch_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    return BatchStatusResponse.model_validate(batch)
