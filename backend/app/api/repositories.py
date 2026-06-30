"""
Repository API — CRUD operations for repositories.
"""
import logging
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Repository, AnalysisResult, Recommendation, RepoStatus
from app.schemas import (
    RepositoryResponse, RepositoryListResponse,
    RepositoryDetailResponse, AnalysisResultResponse, RecommendationResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/repositories", response_model=RepositoryListResponse)
async def list_repositories(
    status: Optional[str] = Query(None, description="Filter by status"),
    feasibility: Optional[str] = Query(None, description="Filter by feasibility class"),
    search: Optional[str] = Query(None, description="Search by name or owner"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all repositories with optional filters."""
    query = select(Repository).order_by(Repository.created_at.desc())

    if status:
        query = query.where(Repository.status == status)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (Repository.name.ilike(search_pattern)) |
            (Repository.owner.ilike(search_pattern))
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    repos = result.scalars().all()

    repo_responses = []
    for repo in repos:
        repo_responses.append(RepositoryResponse.model_validate(repo))

    return RepositoryListResponse(total=total, repositories=repo_responses)


@router.get("/repositories/{repo_id}", response_model=RepositoryDetailResponse)
async def get_repository(
    repo_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed repository information including analysis results."""
    result = await db.execute(
        select(Repository)
        .options(
            selectinload(Repository.analysis)
            .selectinload(AnalysisResult.recommendations)
        )
        .where(Repository.id == repo_id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    repo_response = RepositoryResponse.model_validate(repo)

    analysis_response = None
    if repo.analysis:
        recs = [
            RecommendationResponse.model_validate(r)
            for r in repo.analysis.recommendations
        ]
        analysis_response = AnalysisResultResponse(
            id=repo.analysis.id,
            repo_id=repo.analysis.repo_id,
            languages=repo.analysis.languages or {},
            frameworks=repo.analysis.frameworks or [],
            dependencies=repo.analysis.dependencies or {},
            tech_layers=repo.analysis.tech_layers or {},
            detected_files=repo.analysis.detected_files or [],
            readme_summary=repo.analysis.readme_summary,
            build_status=repo.analysis.build_status,
            build_logs=repo.analysis.build_logs,
            build_duration_seconds=repo.analysis.build_duration_seconds,
            feasibility_score=repo.analysis.feasibility_score,
            feasibility_class=repo.analysis.feasibility_class,
            score_breakdown=repo.analysis.score_breakdown or {},
            security_score=repo.analysis.security_score,
            recommendations=recs,
            created_at=repo.analysis.created_at,
        )

    return RepositoryDetailResponse(
        repository=repo_response,
        analysis=analysis_response,
    )


@router.delete("/repositories/{repo_id}")
async def delete_repository(
    repo_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a repository and its analysis results."""
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    await db.delete(repo)
    await db.commit()

    return {"message": f"Repository {repo.owner}/{repo.name} deleted"}

@router.post("/recommendations/{rec_id}/auto-fix")
async def auto_fix_recommendation(
    rec_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Automatically create a PR for a specific recommendation."""
    # Fetch recommendation
    result = await db.execute(
        select(Recommendation)
        .options(selectinload(Recommendation.analysis).selectinload(AnalysisResult.repository))
        .where(Recommendation.id == rec_id)
    )
    rec = result.scalar_one_or_none()
    
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
        
    analysis = rec.analysis
    repo = analysis.repository
    
    # Import here to avoid circular imports if any
    from app.services.pr_generator import PRGenerator
    
    try:
        generator = PRGenerator()
        rec_dict = {
            "title": rec.title,
            "description": rec.description,
            "fix": rec.fix,
            "category": rec.category
        }
        
        pr_url = await generator.create_auto_fix_pr(
            owner=repo.owner,
            repo_name=repo.name,
            recommendation=rec_dict,
            detected_files=analysis.detected_files
        )
        
        return {"success": True, "pr_url": pr_url}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Auto-fix failed: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
