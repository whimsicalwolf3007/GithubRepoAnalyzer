"""
Analysis Pipeline — Orchestrates the full repository analysis workflow.
Coordinates all engines: Input → Scrape → Tech Stack → Build → Feasibility → AI Recommend → Save
"""
import logging
from typing import Optional
from uuid import UUID
from dataclasses import asdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import Repository, AnalysisResult, Recommendation, UploadBatch, RepoStatus, BatchStatus
from app.engines.github_scraper import GitHubScraper
from app.engines.tech_stack import identify_tech_stack
from app.engines.build_engine import BuildEngine
from app.engines.feasibility import calculate_feasibility
from app.engines.ai_recommender import AIRecommender, AnalysisContext

logger = logging.getLogger(__name__)

# Singleton instances
_scraper: Optional[GitHubScraper] = None
_build_engine: Optional[BuildEngine] = None
_recommender: Optional[AIRecommender] = None


def get_scraper() -> GitHubScraper:
    global _scraper
    if _scraper is None:
        _scraper = GitHubScraper()
    return _scraper


def get_build_engine() -> BuildEngine:
    global _build_engine
    if _build_engine is None:
        _build_engine = BuildEngine()
    return _build_engine


def get_recommender() -> AIRecommender:
    global _recommender
    if _recommender is None:
        _recommender = AIRecommender()
    return _recommender


async def analyze_single_repository(db: AsyncSession, repo_id: UUID) -> dict:
    """
    Run the full analysis pipeline on a single repository.
    
    Pipeline steps:
    1. GitHub Scraping
    2. Tech Stack Identification
    3. Build Simulation (Docker or rule-based)
    4. Feasibility Scoring
    5. AI-powered Recommendations
    6. Save Results to DB
    """
    # Load repository
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise ValueError(f"Repository not found: {repo_id}")

    logger.info(f"Starting analysis pipeline for {repo.owner}/{repo.name}")

    try:
        # ── Step 1: GitHub Scraping ──────────────────────────
        repo.status = RepoStatus.SCRAPING
        await db.commit()

        scraper = get_scraper()
        scrape_data = await scraper.scrape_repository(repo.owner, repo.name)

        # Update repo metadata
        metadata = scrape_data.get("metadata", {})
        repo.description = metadata.get("description", "")
        repo.stars = metadata.get("stars", 0)
        repo.forks = metadata.get("forks", 0)
        repo.default_branch = metadata.get("default_branch", "main")

        # ── Step 2: Tech Stack Identification ────────────────
        repo.status = RepoStatus.ANALYZING
        await db.commit()

        tech_data = identify_tech_stack(scrape_data)

        # ── Step 3: Build Simulation ─────────────────────────
        repo.status = RepoStatus.BUILDING
        await db.commit()

        build_engine = get_build_engine()
        build_result = await build_engine.build_in_docker(
            owner=repo.owner,
            repo=repo.name,
            languages=tech_data["languages"],
            detected_files=scrape_data.get("detected_files", []),
        )

        # ── Step 4: Feasibility Scoring ──────────────────────
        feasibility_result = calculate_feasibility(
            detected_files=scrape_data.get("detected_files", []),
            dependencies=tech_data.get("dependencies", {}),
            tech_layers=tech_data.get("tech_layers", {}),
            ci_cd_files=scrape_data.get("ci_cd_files", []),
            readme=scrape_data.get("readme", ""),
            build_status=build_result.get("build_status", "skipped"),
        )

        # ── Step 5: AI Recommendations ───────────────────────
        context = AnalysisContext(
            repo_name=f"{repo.owner}/{repo.name}",
            repo_url=repo.url,
            languages=tech_data.get("languages", {}),
            frameworks=tech_data.get("frameworks", []),
            dependencies=tech_data.get("dependencies", {}),
            detected_files=scrape_data.get("detected_files", []),
            build_status=build_result.get("build_status", ""),
            build_logs=build_result.get("build_logs", ""),
            readme_summary=scrape_data.get("readme", "")[:1000] if scrape_data.get("readme") else "",
            feasibility_score=feasibility_result["score"],
        )

        recommender = get_recommender()
        ai_recommendations = await recommender.get_recommendations(context)

        # ── Step 6: Save Results ─────────────────────────────
        # Delete existing analysis if re-analyzing
        existing = await db.execute(
            select(AnalysisResult).where(AnalysisResult.repo_id == repo.id)
        )
        existing_analysis = existing.scalar_one_or_none()
        if existing_analysis:
            await db.delete(existing_analysis)
            await db.flush()

        # Calculate Security Score
        security_score = 100.0
        for rec in ai_recommendations:
            if rec.category == "security":
                if rec.severity == "critical":
                    security_score -= 25.0
                elif rec.severity == "high":
                    security_score -= 15.0
                elif rec.severity == "medium":
                    security_score -= 5.0
        security_score = max(0.0, security_score)

        analysis = AnalysisResult(
            repo_id=repo.id,
            languages=tech_data.get("languages", {}),
            frameworks=tech_data.get("frameworks", []),
            dependencies=tech_data.get("dependencies", {}),
            tech_layers=tech_data.get("tech_layers", {}),
            detected_files=scrape_data.get("detected_files", []),
            readme_summary=scrape_data.get("readme", "")[:2000] if scrape_data.get("readme") else None,
            build_status=build_result.get("build_status", "skipped"),
            build_logs=build_result.get("build_logs", ""),
            build_duration_seconds=build_result.get("build_duration_seconds", 0),
            feasibility_score=feasibility_result["score"],
            feasibility_class=feasibility_result["feasibility_class"],
            score_breakdown=feasibility_result["breakdown"],
            security_score=security_score,
        )
        db.add(analysis)
        await db.flush()  # Get the analysis ID

        # Save recommendations
        for rec in ai_recommendations:
            db_rec = Recommendation(
                analysis_id=analysis.id,
                category=rec.category,
                severity=rec.severity,
                title=rec.title,
                description=rec.description,
                fix=rec.fix,
                effort=rec.effort,
                estimated_time=rec.estimated_time,
                ai_provider=rec.ai_provider,
            )
            db.add(db_rec)

        repo.status = RepoStatus.COMPLETED
        repo.error_message = None
        await db.commit()

        logger.info(
            f"Analysis complete for {repo.owner}/{repo.name}: "
            f"score={feasibility_result['score']}, "
            f"class={feasibility_result['feasibility_class'].value}, "
            f"recommendations={len(ai_recommendations)}"
        )

        return {
            "repo_id": str(repo.id),
            "status": "completed",
            "feasibility_score": feasibility_result["score"],
            "feasibility_class": feasibility_result["feasibility_class"].value,
            "recommendations_count": len(ai_recommendations),
        }

    except Exception as e:
        logger.error(f"Analysis failed for {repo.owner}/{repo.name}: {e}")
        repo.status = RepoStatus.FAILED
        repo.error_message = str(e)[:500]
        await db.commit()
        return {
            "repo_id": str(repo.id),
            "status": "failed",
            "error": str(e),
        }


async def analyze_batch(db: AsyncSession, batch_id: UUID) -> dict:
    """
    Run analysis pipeline on all repositories in a batch.
    """
    result = await db.execute(select(UploadBatch).where(UploadBatch.id == batch_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise ValueError(f"Batch not found: {batch_id}")

    batch.status = BatchStatus.PROCESSING
    await db.commit()

    # Get all repos in batch
    repos_result = await db.execute(
        select(Repository).where(Repository.batch_id == batch_id)
    )
    repos = repos_result.scalars().all()

    results = []
    for repo in repos:
        try:
            result = await analyze_single_repository(db, repo.id)
            results.append(result)
            batch.processed_count += 1
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to analyze {repo.owner}/{repo.name}: {e}")
            results.append({"repo_id": str(repo.id), "status": "failed", "error": str(e)})

    batch.status = BatchStatus.COMPLETED
    await db.commit()

    completed = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") == "failed")

    logger.info(f"Batch {batch_id} complete: {completed} succeeded, {failed} failed")
    return {
        "batch_id": str(batch_id),
        "total": len(repos),
        "completed": completed,
        "failed": failed,
        "results": results,
    }
