"""
Feasibility Analysis Engine — Scores repositories on buildability.
Uses a weighted scoring system across multiple dimensions.
"""
import logging
from typing import Dict, Any, List
from app.models import FeasibilityClass

logger = logging.getLogger(__name__)

# ── Scoring weights ──────────────────────────────────────────

SCORING_CRITERIA = {
    "dependency_files": {
        "weight": 20,
        "description": "Dependency management files present",
    },
    "build_config": {
        "weight": 20,
        "description": "Build configuration and scripts",
    },
    "docker_support": {
        "weight": 15,
        "description": "Docker/containerization support",
    },
    "ci_cd": {
        "weight": 10,
        "description": "CI/CD pipeline configuration",
    },
    "documentation": {
        "weight": 10,
        "description": "README and documentation quality",
    },
    "build_result": {
        "weight": 25,
        "description": "Actual or simulated build result",
    },
}


def _score_dependency_files(detected_files: List[str], dependencies: Dict) -> float:
    """Score based on presence and quality of dependency files."""
    dep_files = [
        "requirements.txt", "package.json", "pom.xml", "build.gradle",
        "Gemfile", "go.mod", "Cargo.toml", "pyproject.toml", "Pipfile",
        "composer.json", "mix.exs", "pubspec.yaml", "setup.py", "setup.cfg",
    ]
    
    found = [f for f in dep_files if f in detected_files]
    if not found:
        return 0.0

    score = 50.0  # Base score for having at least one dep file

    # Bonus for lock files (indicates reproducible builds)
    lock_files = ["package-lock.json", "yarn.lock", "Pipfile.lock", "Cargo.lock", "go.sum", "Gemfile.lock"]
    if any(f in detected_files for f in lock_files):
        score += 25.0

    # Bonus if dependencies were actually parsed
    if dependencies and any(len(v) > 0 for v in dependencies.values() if isinstance(v, list)):
        score += 25.0

    return min(score, 100.0)


def _score_build_config(detected_files: List[str], tech_layers: Dict) -> float:
    """Score based on build configuration files."""
    build_indicators = [
        "Makefile", "Rakefile", "Taskfile.yml", "justfile",
        "webpack.config.js", "vite.config.js", "tsconfig.json",
        "babel.config.js", ".babelrc", "rollup.config.js",
        "setup.py", "setup.cfg", "build.gradle", "pom.xml",
    ]

    found = [f for f in build_indicators if f in detected_files]
    if not found and not any(
        f in detected_files for f in ["package.json", "requirements.txt", "go.mod", "Cargo.toml"]
    ):
        return 0.0

    score = 40.0 if found else 20.0

    # Check for build scripts in package.json
    if "package.json" in detected_files:
        score += 30.0

    if len(found) >= 2:
        score += 30.0
    elif len(found) == 1:
        score += 15.0

    return min(score, 100.0)


def _score_docker_support(detected_files: List[str]) -> float:
    """Score based on Docker/containerization support."""
    score = 0.0

    if "Dockerfile" in detected_files:
        score += 60.0
    if any("docker-compose" in f for f in detected_files):
        score += 25.0
    if ".dockerignore" in detected_files:
        score += 15.0

    return min(score, 100.0)


def _score_ci_cd(detected_files: List[str], ci_cd_files: List[str]) -> float:
    """Score based on CI/CD pipeline configuration."""
    if not ci_cd_files:
        return 0.0

    score = 60.0  # Base for having any CI/CD

    if len(ci_cd_files) >= 2:
        score += 40.0
    elif ".github/workflows" in ci_cd_files:
        score += 30.0
    else:
        score += 20.0

    return min(score, 100.0)


def _score_documentation(readme: str, detected_files: List[str]) -> float:
    """Score based on README and documentation quality."""
    score = 0.0

    if readme:
        # Base score for having a README
        score += 40.0

        readme_length = len(readme)
        if readme_length > 2000:
            score += 30.0
        elif readme_length > 500:
            score += 20.0
        elif readme_length > 100:
            score += 10.0

        # Check for key sections
        lower = readme.lower()
        if "install" in lower or "setup" in lower or "getting started" in lower:
            score += 15.0
        if "usage" in lower or "example" in lower:
            score += 10.0
        if "contributing" in lower or "license" in lower:
            score += 5.0

    # Check for other doc files
    doc_files = ["CONTRIBUTING.md", "CHANGELOG.md", "LICENSE", "docs"]
    found_docs = [f for f in doc_files if any(f.lower() in d.lower() for d in detected_files)]
    score += min(len(found_docs) * 5, 15)

    return min(score, 100.0)


def _score_build_result(build_status: str) -> float:
    """Score based on actual or simulated build result."""
    if build_status == "success":
        return 100.0
    elif build_status == "failed":
        return 20.0  # Partial credit for attempting
    elif build_status == "timeout":
        return 30.0
    elif build_status == "skipped":
        return 40.0  # Neutral — couldn't determine
    else:
        return 0.0


def calculate_feasibility(
    detected_files: List[str],
    dependencies: Dict,
    tech_layers: Dict,
    ci_cd_files: List[str],
    readme: str,
    build_status: str,
) -> Dict[str, Any]:
    """
    Calculate the feasibility score and classification for a repository.
    
    Returns:
    {
        "score": float (0-100),
        "feasibility_class": FeasibilityClass,
        "breakdown": {criterion: {score, weight, weighted_score, description}}
    }
    """
    breakdown = {}

    # Calculate each criterion
    scores = {
        "dependency_files": _score_dependency_files(detected_files, dependencies),
        "build_config": _score_build_config(detected_files, tech_layers),
        "docker_support": _score_docker_support(detected_files),
        "ci_cd": _score_ci_cd(detected_files, ci_cd_files),
        "documentation": _score_documentation(readme or "", detected_files),
        "build_result": _score_build_result(build_status),
    }

    total_score = 0.0
    for criterion, raw_score in scores.items():
        weight = SCORING_CRITERIA[criterion]["weight"]
        weighted = (raw_score / 100.0) * weight
        total_score += weighted
        breakdown[criterion] = {
            "raw_score": round(raw_score, 1),
            "weight": weight,
            "weighted_score": round(weighted, 1),
            "description": SCORING_CRITERIA[criterion]["description"],
        }

    # Classify
    total_score = round(total_score, 1)
    if total_score >= 75:
        feasibility_class = FeasibilityClass.BUILDABLE
    elif total_score >= 40:
        feasibility_class = FeasibilityClass.BUILDABLE_WITH_FIXES
    else:
        feasibility_class = FeasibilityClass.NOT_BUILDABLE

    result = {
        "score": total_score,
        "feasibility_class": feasibility_class,
        "breakdown": breakdown,
    }

    logger.info(f"Feasibility score: {total_score}/100 ({feasibility_class.value})")
    return result
