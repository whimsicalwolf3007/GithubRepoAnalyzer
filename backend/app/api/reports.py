"""
Reports API — Download Excel reports and JSON exports.
"""
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Repository, AnalysisResult, Recommendation
from app.engines.output_generator import generate_excel_report

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_all_repo_data(db: AsyncSession) -> list:
    """Fetch all repositories with analysis data for report generation."""
    result = await db.execute(
        select(Repository)
        .options(
            selectinload(Repository.analysis)
            .selectinload(AnalysisResult.recommendations)
        )
        .order_by(Repository.created_at.desc())
    )
    repos = result.scalars().all()

    data = []
    for repo in repos:
        repo_dict = {
            "name": repo.name,
            "owner": repo.owner,
            "url": repo.url,
            "description": repo.description,
            "stars": repo.stars,
            "forks": repo.forks,
            "status": repo.status.value if repo.status else "unknown",
        }

        if repo.analysis:
            repo_dict.update({
                "languages": repo.analysis.languages or {},
                "frameworks": repo.analysis.frameworks or [],
                "dependencies": repo.analysis.dependencies or {},
                "tech_layers": repo.analysis.tech_layers or {},
                "detected_files": repo.analysis.detected_files or [],
                "build_status": repo.analysis.build_status,
                "build_logs": repo.analysis.build_logs,
                "feasibility_score": repo.analysis.feasibility_score,
                "feasibility_class": repo.analysis.feasibility_class.value if repo.analysis.feasibility_class else "pending",
                "score_breakdown": repo.analysis.score_breakdown or {},
                "recommendations": [
                    {
                        "category": r.category,
                        "severity": r.severity,
                        "title": r.title,
                        "description": r.description,
                        "fix": r.fix,
                        "effort": r.effort,
                        "estimated_time": r.estimated_time,
                        "ai_provider": r.ai_provider,
                    }
                    for r in repo.analysis.recommendations
                ],
            })
        else:
            repo_dict.update({
                "languages": {},
                "frameworks": [],
                "feasibility_score": 0,
                "feasibility_class": "pending",
                "recommendations": [],
            })

        data.append(repo_dict)

    return data


@router.get("/reports/excel")
async def download_excel_report(db: AsyncSession = Depends(get_db)):
    """Generate and download an Excel report of all analysis results."""
    repo_data = await _get_all_repo_data(db)

    if not repo_data:
        return JSONResponse(
            status_code=404,
            content={"detail": "No repositories found. Upload and analyze repos first."},
        )

    try:
        file_path = generate_excel_report(repo_data)
        return FileResponse(
            path=file_path,
            filename="autodev_intelligence_report.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        logger.error(f"Failed to generate Excel report: {e}")
        return JSONResponse(status_code=500, content={"detail": f"Report generation failed: {e}"})


@router.get("/reports/json")
async def download_json_report(db: AsyncSession = Depends(get_db)):
    """Download all analysis results as JSON."""
    repo_data = await _get_all_repo_data(db)

    if not repo_data:
        return JSONResponse(
            status_code=404,
            content={"detail": "No repositories found"},
        )

    return JSONResponse(content={
        "total_repositories": len(repo_data),
        "repositories": repo_data,
    })
