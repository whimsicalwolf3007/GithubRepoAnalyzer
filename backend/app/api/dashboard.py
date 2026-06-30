"""
Dashboard API — Aggregated statistics and chart data.
"""
import logging
from collections import Counter
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import Repository, AnalysisResult, UploadBatch, RepoStatus, FeasibilityClass
from app.schemas import (
    DashboardStats, DashboardResponse, TechDistributionItem,
    TechDistributionResponse, FeasibilityOverviewResponse, RecentActivityItem,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get aggregated dashboard statistics."""
    # Total repos
    total_result = await db.execute(select(func.count()).select_from(Repository))
    total_repos = total_result.scalar() or 0

    # Buildable count
    buildable_result = await db.execute(
        select(func.count()).select_from(AnalysisResult)
        .where(AnalysisResult.feasibility_class == FeasibilityClass.BUILDABLE)
    )
    buildable = buildable_result.scalar() or 0

    # Buildable with fixes
    fixes_result = await db.execute(
        select(func.count()).select_from(AnalysisResult)
        .where(AnalysisResult.feasibility_class == FeasibilityClass.BUILDABLE_WITH_FIXES)
    )
    buildable_with_fixes = fixes_result.scalar() or 0

    # Not buildable
    not_buildable_result = await db.execute(
        select(func.count()).select_from(AnalysisResult)
        .where(AnalysisResult.feasibility_class == FeasibilityClass.NOT_BUILDABLE)
    )
    not_buildable = not_buildable_result.scalar() or 0

    # In progress
    in_progress_result = await db.execute(
        select(func.count()).select_from(Repository)
        .where(Repository.status.in_([
            RepoStatus.QUEUED, RepoStatus.SCRAPING,
            RepoStatus.ANALYZING, RepoStatus.BUILDING,
        ]))
    )
    in_progress = in_progress_result.scalar() or 0

    # Total batches
    batches_result = await db.execute(select(func.count()).select_from(UploadBatch))
    total_batches = batches_result.scalar() or 0

    # Average score
    avg_result = await db.execute(
        select(func.avg(AnalysisResult.feasibility_score))
    )
    avg_score = avg_result.scalar() or 0.0

    return DashboardStats(
        total_repos=total_repos,
        buildable=buildable,
        buildable_with_fixes=buildable_with_fixes,
        not_buildable=not_buildable,
        in_progress=in_progress,
        total_batches=total_batches,
        avg_feasibility_score=round(float(avg_score), 1),
    )


@router.get("/dashboard/tech-distribution", response_model=TechDistributionResponse)
async def get_tech_distribution(db: AsyncSession = Depends(get_db)):
    """Get language and framework distribution across all analyzed repos."""
    result = await db.execute(select(AnalysisResult))
    analyses = result.scalars().all()

    lang_counter = Counter()
    fw_counter = Counter()

    for analysis in analyses:
        if analysis.languages:
            for lang in analysis.languages.keys():
                lang_counter[lang] += 1
        if analysis.frameworks:
            for fw in analysis.frameworks:
                fw_counter[fw] += 1

    total = len(analyses) or 1

    languages = [
        TechDistributionItem(
            name=name, count=count,
            percentage=round(count / total * 100, 1)
        )
        for name, count in lang_counter.most_common(15)
    ]

    frameworks = [
        TechDistributionItem(
            name=name, count=count,
            percentage=round(count / total * 100, 1)
        )
        for name, count in fw_counter.most_common(15)
    ]

    return TechDistributionResponse(languages=languages, frameworks=frameworks)


@router.get("/dashboard/feasibility-overview", response_model=FeasibilityOverviewResponse)
async def get_feasibility_overview(db: AsyncSession = Depends(get_db)):
    """Get feasibility classification breakdown and score distribution."""
    result = await db.execute(select(AnalysisResult))
    analyses = result.scalars().all()

    buildable = sum(1 for a in analyses if a.feasibility_class == FeasibilityClass.BUILDABLE)
    fixes = sum(1 for a in analyses if a.feasibility_class == FeasibilityClass.BUILDABLE_WITH_FIXES)
    not_buildable = sum(1 for a in analyses if a.feasibility_class == FeasibilityClass.NOT_BUILDABLE)

    # Total repos without analysis yet
    total_repos_result = await db.execute(select(func.count()).select_from(Repository))
    total_repos = total_repos_result.scalar() or 0
    pending = total_repos - len(analyses)

    # Score distribution in ranges
    ranges = [
        ("0-20", 0, 20), ("21-40", 21, 40), ("41-60", 41, 60),
        ("61-80", 61, 80), ("81-100", 81, 100)
    ]
    score_dist = []
    for label, low, high in ranges:
        count = sum(1 for a in analyses if low <= a.feasibility_score <= high)
        score_dist.append({"range": label, "count": count})

    return FeasibilityOverviewResponse(
        buildable=buildable,
        buildable_with_fixes=fixes,
        not_buildable=not_buildable,
        pending=pending,
        score_distribution=score_dist,
    )


@router.get("/dashboard/recent-activity")
async def get_recent_activity(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Get recent analysis activity."""
    result = await db.execute(
        select(Repository)
        .order_by(Repository.updated_at.desc())
        .limit(limit)
    )
    repos = result.scalars().all()

    activities = []
    for repo in repos:
        # Get analysis if exists
        analysis_result = await db.execute(
            select(AnalysisResult).where(AnalysisResult.repo_id == repo.id)
        )
        analysis = analysis_result.scalar_one_or_none()

        activities.append({
            "repo_name": f"{repo.owner}/{repo.name}",
            "repo_url": repo.url,
            "repo_id": str(repo.id),
            "status": repo.status.value if repo.status else "unknown",
            "feasibility_class": analysis.feasibility_class.value if analysis and analysis.feasibility_class else None,
            "feasibility_score": analysis.feasibility_score if analysis else None,
            "timestamp": repo.updated_at.isoformat() if repo.updated_at else None,
        })

    return activities
