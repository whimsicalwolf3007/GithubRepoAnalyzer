"""
GitHub Scraping Engine — Async GitHub REST API client.
Extracts repository metadata, languages, dependency files, README, and CI/CD configs.
"""
import base64
import logging
from typing import Optional, Dict, List, Any
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# Dependency files to look for in repositories
DEPENDENCY_FILES = [
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    "pyproject.toml",
    "Pipfile",
    "package.json",
    "yarn.lock",
    "package-lock.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Gemfile",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "composer.json",
    "mix.exs",
    "pubspec.yaml",
    "CMakeLists.txt",
    "Makefile",
]

# Build / DevOps files to check
BUILD_FILES = [
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".dockerignore",
    "Makefile",
    "Rakefile",
    "Taskfile.yml",
    "justfile",
]

CI_CD_FILES = [
    ".github/workflows",
    ".gitlab-ci.yml",
    ".travis.yml",
    "Jenkinsfile",
    ".circleci/config.yml",
    "azure-pipelines.yml",
    "bitbucket-pipelines.yml",
]


class GitHubScraper:
    """Async GitHub REST API client for repository analysis."""

    def __init__(self):
        self.base_url = settings.GITHUB_API_BASE
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AutoDev-Intelligence/1.0",
        }
        if settings.GITHUB_TOKEN:
            self.headers["Authorization"] = f"token {settings.GITHUB_TOKEN}"

    async def _request(self, endpoint: str) -> Optional[Any]:
        """Make an authenticated request to the GitHub API."""
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    logger.warning(f"Not found: {endpoint}")
                    return None
                elif response.status_code == 403:
                    remaining = response.headers.get("x-ratelimit-remaining", "?")
                    logger.error(f"Rate limited. Remaining: {remaining}")
                    return None
                else:
                    logger.error(f"GitHub API error {response.status_code}: {endpoint}")
                    return None
            except httpx.TimeoutException:
                logger.error(f"Timeout requesting: {endpoint}")
                return None
            except Exception as e:
                logger.error(f"Request failed for {endpoint}: {e}")
                return None

    async def get_repo_metadata(self, owner: str, repo: str) -> Optional[Dict]:
        """Fetch repository metadata (description, stars, forks, topics, etc.)."""
        data = await self._request(f"/repos/{owner}/{repo}")
        if not data:
            return None

        return {
            "description": data.get("description", ""),
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "default_branch": data.get("default_branch", "main"),
            "topics": data.get("topics", []),
            "license": data.get("license", {}).get("name") if data.get("license") else None,
            "size": data.get("size", 0),
            "open_issues": data.get("open_issues_count", 0),
            "archived": data.get("archived", False),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "homepage": data.get("homepage"),
        }

    async def get_languages(self, owner: str, repo: str) -> Dict[str, int]:
        """Fetch language breakdown (language -> bytes of code)."""
        data = await self._request(f"/repos/{owner}/{repo}/languages")
        return data if data else {}

    async def get_readme(self, owner: str, repo: str) -> Optional[str]:
        """Fetch and decode the README content."""
        data = await self._request(f"/repos/{owner}/{repo}/readme")
        if data and "content" in data:
            try:
                content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
                # Truncate very long READMEs
                return content[:5000] if len(content) > 5000 else content
            except Exception:
                return None
        return None

    async def get_file_tree(self, owner: str, repo: str, path: str = "") -> List[Dict]:
        """List contents of a directory in the repository."""
        data = await self._request(f"/repos/{owner}/{repo}/contents/{path}")
        if isinstance(data, list):
            return [{"name": f["name"], "type": f["type"], "path": f["path"]} for f in data]
        return []

    async def get_file_content(self, owner: str, repo: str, path: str) -> Optional[str]:
        """Fetch and decode the content of a specific file."""
        data = await self._request(f"/repos/{owner}/{repo}/contents/{path}")
        if data and isinstance(data, dict) and "content" in data:
            try:
                return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            except Exception:
                return None
        return None

    async def check_file_exists(self, owner: str, repo: str, path: str) -> bool:
        """Check if a file or directory exists in the repository."""
        data = await self._request(f"/repos/{owner}/{repo}/contents/{path}")
        return data is not None

    async def scrape_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Full repository scrape — fetches all relevant data.
        Returns a comprehensive dict with metadata, languages, files, and content.
        """
        logger.info(f"Scraping repository: {owner}/{repo}")

        # Fetch metadata and languages concurrently
        metadata = await self.get_repo_metadata(owner, repo)
        if not metadata:
            raise ValueError(f"Repository not found: {owner}/{repo}")

        languages = await self.get_languages(owner, repo)
        readme = await self.get_readme(owner, repo)
        root_files = await self.get_file_tree(owner, repo)

        # Get file names in root
        root_file_names = [f["name"] for f in root_files]
        root_dir_names = [f["name"] for f in root_files if f["type"] == "dir"]

        # Check for dependency files
        found_dep_files = {}
        for dep_file in DEPENDENCY_FILES:
            if dep_file in root_file_names:
                content = await self.get_file_content(owner, repo, dep_file)
                if content:
                    found_dep_files[dep_file] = content

        # Check for build files
        found_build_files = []
        for build_file in BUILD_FILES:
            if build_file in root_file_names:
                found_build_files.append(build_file)

        # Check for CI/CD configs
        found_ci_files = []
        for ci_file in CI_CD_FILES:
            if ci_file in root_file_names or ci_file in root_dir_names:
                found_ci_files.append(ci_file)
            elif "/" in ci_file:
                # Check subdirectory files like .github/workflows
                exists = await self.check_file_exists(owner, repo, ci_file)
                if exists:
                    found_ci_files.append(ci_file)

        # Build all detected files list
        all_detected = list(found_dep_files.keys()) + found_build_files + found_ci_files

        result = {
            "metadata": metadata,
            "languages": languages,
            "readme": readme,
            "root_files": root_file_names,
            "dependency_files": found_dep_files,
            "build_files": found_build_files,
            "ci_cd_files": found_ci_files,
            "detected_files": all_detected,
        }

        logger.info(
            f"Scraped {owner}/{repo}: {len(languages)} languages, "
            f"{len(found_dep_files)} dep files, {len(found_build_files)} build files"
        )
        return result
