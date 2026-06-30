"""
Tech Stack Identification Engine — Identifies programming languages, frameworks,
tools, and databases from repository data. Builds structured output with layers:
Frontend, Backend, Database, and DevOps.
"""
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# ── Framework Detection Rules ──────────────────────────────────────────

# Maps dependency names to framework names, grouped by ecosystem
PYTHON_FRAMEWORKS = {
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "tornado": "Tornado",
    "pyramid": "Pyramid",
    "bottle": "Bottle",
    "sanic": "Sanic",
    "starlette": "Starlette",
    "streamlit": "Streamlit",
    "dash": "Dash",
    "celery": "Celery",
    "scrapy": "Scrapy",
    "pytest": "Pytest",
    "numpy": "NumPy",
    "pandas": "Pandas",
    "tensorflow": "TensorFlow",
    "torch": "PyTorch",
    "scikit-learn": "Scikit-learn",
    "keras": "Keras",
    "opencv-python": "OpenCV",
    "sqlalchemy": "SQLAlchemy",
    "alembic": "Alembic",
}

NODE_FRAMEWORKS = {
    "react": "React",
    "react-dom": "React",
    "next": "Next.js",
    "vue": "Vue.js",
    "nuxt": "Nuxt.js",
    "angular": "Angular",
    "@angular/core": "Angular",
    "svelte": "Svelte",
    "express": "Express.js",
    "nestjs": "NestJS",
    "@nestjs/core": "NestJS",
    "koa": "Koa",
    "fastify": "Fastify",
    "gatsby": "Gatsby",
    "remix": "Remix",
    "tailwindcss": "TailwindCSS",
    "bootstrap": "Bootstrap",
    "webpack": "Webpack",
    "vite": "Vite",
    "jest": "Jest",
    "mocha": "Mocha",
    "typescript": "TypeScript",
    "electron": "Electron",
    "prisma": "Prisma",
    "sequelize": "Sequelize",
    "mongoose": "Mongoose",
    "typeorm": "TypeORM",
}

JAVA_FRAMEWORKS = {
    "spring-boot": "Spring Boot",
    "spring-core": "Spring",
    "hibernate": "Hibernate",
    "junit": "JUnit",
    "maven": "Maven",
    "gradle": "Gradle",
}

# Database detection from dependency files
DATABASE_INDICATORS = {
    "psycopg2": "PostgreSQL",
    "psycopg2-binary": "PostgreSQL",
    "asyncpg": "PostgreSQL",
    "pg": "PostgreSQL",
    "mysql-connector": "MySQL",
    "pymysql": "MySQL",
    "mysql2": "MySQL",
    "pymongo": "MongoDB",
    "mongodb": "MongoDB",
    "mongoose": "MongoDB",
    "redis": "Redis",
    "ioredis": "Redis",
    "aioredis": "Redis",
    "sqlite3": "SQLite",
    "better-sqlite3": "SQLite",
    "aiosqlite": "SQLite",
    "cassandra-driver": "Cassandra",
    "elasticsearch": "Elasticsearch",
    "neo4j": "Neo4j",
}

# Language to category mapping
FRONTEND_LANGUAGES = {"JavaScript", "TypeScript", "HTML", "CSS", "SCSS", "Vue", "Svelte"}
BACKEND_LANGUAGES = {"Python", "Java", "Go", "Ruby", "Rust", "C#", "PHP", "Kotlin", "Scala", "Elixir"}


def _parse_requirements_txt(content: str) -> List[str]:
    """Parse Python requirements.txt and extract package names."""
    packages = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Remove version specifiers
        name = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split("!=")[0].split("[")[0]
        name = name.strip().lower()
        if name:
            packages.append(name)
    return packages


def _parse_package_json(content: str) -> List[str]:
    """Parse Node.js package.json and extract dependency names."""
    packages = []
    try:
        data = json.loads(content)
        for key in ["dependencies", "devDependencies", "peerDependencies"]:
            if key in data:
                packages.extend(data[key].keys())
    except json.JSONDecodeError:
        pass
    return [p.lower() for p in packages]


def _parse_pyproject_toml(content: str) -> List[str]:
    """Parse pyproject.toml for dependencies (simplified parser)."""
    packages = []
    in_deps = False
    for line in content.splitlines():
        line = line.strip()
        if "dependencies" in line and "=" in line:
            in_deps = True
            continue
        if in_deps:
            if line.startswith("]"):
                in_deps = False
                continue
            # Extract package name from quoted strings
            if '"' in line:
                pkg = line.strip(' ",')
                name = pkg.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split("[")[0]
                if name:
                    packages.append(name.lower())
    return packages


def _parse_pom_xml(content: str) -> List[str]:
    """Very basic POM XML parser to extract artifactIds."""
    import re
    artifacts = re.findall(r"<artifactId>(.*?)</artifactId>", content)
    return [a.lower() for a in artifacts]


def _parse_go_mod(content: str) -> List[str]:
    """Parse go.mod for module dependencies."""
    modules = []
    in_require = False
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("require ("):
            in_require = True
            continue
        if in_require and line == ")":
            in_require = False
            continue
        if in_require:
            parts = line.split()
            if parts:
                modules.append(parts[0].split("/")[-1].lower())
    return modules


def identify_tech_stack(scrape_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze scraped repository data and identify the complete tech stack.
    
    Returns a structured dict with:
    - languages: {name: bytes, ...}
    - frameworks: [name, ...]
    - dependencies: {ecosystem: [dep, ...]}
    - databases: [name, ...]
    - tech_layers: {frontend: {...}, backend: {...}, database: {...}, devops: {...}}
    """
    languages = scrape_data.get("languages", {})
    dep_files = scrape_data.get("dependency_files", {})
    build_files = scrape_data.get("build_files", [])
    ci_cd_files = scrape_data.get("ci_cd_files", [])

    frameworks = set()
    all_deps = {}
    databases = set()

    # ── Parse dependency files ──────────────────────────────────────

    # Python
    if "requirements.txt" in dep_files:
        pkgs = _parse_requirements_txt(dep_files["requirements.txt"])
        all_deps["python"] = pkgs
        for pkg in pkgs:
            if pkg in PYTHON_FRAMEWORKS:
                frameworks.add(PYTHON_FRAMEWORKS[pkg])
            if pkg in DATABASE_INDICATORS:
                databases.add(DATABASE_INDICATORS[pkg])

    if "pyproject.toml" in dep_files:
        pkgs = _parse_pyproject_toml(dep_files["pyproject.toml"])
        all_deps.setdefault("python", []).extend(pkgs)
        for pkg in pkgs:
            if pkg in PYTHON_FRAMEWORKS:
                frameworks.add(PYTHON_FRAMEWORKS[pkg])
            if pkg in DATABASE_INDICATORS:
                databases.add(DATABASE_INDICATORS[pkg])

    # Node.js
    if "package.json" in dep_files:
        pkgs = _parse_package_json(dep_files["package.json"])
        all_deps["node"] = pkgs
        for pkg in pkgs:
            if pkg in NODE_FRAMEWORKS:
                frameworks.add(NODE_FRAMEWORKS[pkg])
            if pkg in DATABASE_INDICATORS:
                databases.add(DATABASE_INDICATORS[pkg])

    # Java (Maven)
    if "pom.xml" in dep_files:
        pkgs = _parse_pom_xml(dep_files["pom.xml"])
        all_deps["java"] = pkgs
        for pkg in pkgs:
            if pkg in JAVA_FRAMEWORKS:
                frameworks.add(JAVA_FRAMEWORKS[pkg])

    # Go
    if "go.mod" in dep_files:
        pkgs = _parse_go_mod(dep_files["go.mod"])
        all_deps["go"] = pkgs

    # Rust (Cargo.toml - basic)
    if "Cargo.toml" in dep_files:
        all_deps["rust"] = ["cargo"]

    # ── Build layers ──────────────────────────────────────

    # Determine primary language
    total_bytes = sum(languages.values()) if languages else 1
    lang_percentages = {lang: round(b / total_bytes * 100, 1) for lang, b in languages.items()}

    # Frontend layer
    frontend = {
        "languages": [l for l in languages if l in FRONTEND_LANGUAGES],
        "frameworks": [],
        "build_tools": [],
    }
    frontend_fw = {"React", "Vue.js", "Angular", "Svelte", "Next.js", "Nuxt.js", "Gatsby", "Remix"}
    frontend["frameworks"] = [f for f in frameworks if f in frontend_fw]
    if "Webpack" in frameworks:
        frontend["build_tools"].append("Webpack")
    if "Vite" in frameworks:
        frontend["build_tools"].append("Vite")

    # Backend layer
    backend = {
        "languages": [l for l in languages if l in BACKEND_LANGUAGES],
        "frameworks": [],
    }
    backend_fw = {"Django", "Flask", "FastAPI", "Express.js", "NestJS", "Spring Boot", "Koa", "Fastify", "Tornado", "Sanic"}
    backend["frameworks"] = [f for f in frameworks if f in backend_fw]

    # Database layer
    database = {
        "databases": list(databases),
        "orms": [],
    }
    orm_names = {"SQLAlchemy", "Alembic", "Prisma", "Sequelize", "Mongoose", "TypeORM", "Hibernate"}
    database["orms"] = [f for f in frameworks if f in orm_names]

    # DevOps layer
    devops = {
        "containerization": [],
        "ci_cd": [],
        "build_files": build_files,
    }
    if any("Dockerfile" in f for f in build_files):
        devops["containerization"].append("Docker")
    if any("docker-compose" in f for f in build_files):
        devops["containerization"].append("Docker Compose")
    devops["ci_cd"] = ci_cd_files

    result = {
        "languages": languages,
        "language_percentages": lang_percentages,
        "frameworks": sorted(list(frameworks)),
        "dependencies": all_deps,
        "databases": list(databases),
        "tech_layers": {
            "frontend": frontend,
            "backend": backend,
            "database": database,
            "devops": devops,
        },
    }

    logger.info(f"Identified tech stack: {len(frameworks)} frameworks, {len(databases)} databases")
    return result
