"""
Build & Execution Engine — Docker sandbox for building repositories.
Uses Docker SDK to clone, install dependencies, and run builds in isolated containers.
Falls back to rule-based static analysis when Docker is unavailable.
"""
import logging
import time
from typing import Dict, Any, Optional, Tuple
from app.config import settings

logger = logging.getLogger(__name__)


# ── Build strategies per tech stack ──────────────────────────────────

BUILD_STRATEGIES = {
    "Python": {
        "image": "python:3.11-slim",
        "install_cmd": "pip install -r requirements.txt --no-cache-dir",
        "build_cmd": "python -m py_compile $(find . -name '*.py' -not -path './venv/*')",
        "dep_file": "requirements.txt",
        "alt_dep_files": ["setup.py", "pyproject.toml", "Pipfile"],
    },
    "JavaScript": {
        "image": "node:20-slim",
        "install_cmd": "npm install",
        "build_cmd": "npm run build --if-present",
        "dep_file": "package.json",
        "alt_dep_files": [],
    },
    "TypeScript": {
        "image": "node:20-slim",
        "install_cmd": "npm install",
        "build_cmd": "npm run build --if-present",
        "dep_file": "package.json",
        "alt_dep_files": [],
    },
    "Java": {
        "image": "maven:3.9-eclipse-temurin-17",
        "install_cmd": "mvn dependency:resolve -q",
        "build_cmd": "mvn compile -q",
        "dep_file": "pom.xml",
        "alt_dep_files": ["build.gradle", "build.gradle.kts"],
    },
    "Go": {
        "image": "golang:1.22-alpine",
        "install_cmd": "go mod download",
        "build_cmd": "go build ./...",
        "dep_file": "go.mod",
        "alt_dep_files": [],
    },
    "Rust": {
        "image": "rust:1.77-slim",
        "install_cmd": "cargo fetch",
        "build_cmd": "cargo check",
        "dep_file": "Cargo.toml",
        "alt_dep_files": [],
    },
    "Ruby": {
        "image": "ruby:3.3-slim",
        "install_cmd": "bundle install",
        "build_cmd": "ruby -c $(find . -name '*.rb')",
        "dep_file": "Gemfile",
        "alt_dep_files": [],
    },
}


class BuildEngine:
    """Docker-based build engine for repository build simulation."""

    def __init__(self):
        self.docker_client = None
        self.docker_available = False
        self._init_docker()

    def _init_docker(self):
        """Initialize Docker client, gracefully handle if Docker is not available."""
        try:
            import docker
            self.docker_client = docker.from_env()
            self.docker_client.ping()
            self.docker_available = True
            logger.info("Docker client initialized successfully")
        except Exception as e:
            logger.warning(f"Docker not available, using rule-based analysis: {e}")
            self.docker_available = False

    def _get_strategy(self, languages: Dict[str, int], detected_files: list) -> Optional[Dict]:
        """Determine the best build strategy based on detected languages and files."""
        if not languages:
            # If no language is detected but a Dockerfile exists, use safe fallback checks.
            if "Dockerfile" in detected_files:
                return {
                    "type": "dockerfile",
                    "image": None,
                    "install_cmd": None,
                    "build_cmd": None,
                }
            return None

        # Sort languages by bytes of code (descending)
        sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)

        # Dockerfile-only repositories are handled via rule-based checks.
        # Running nested docker build commands inside a generic container is fragile.
        if "Dockerfile" in detected_files:
            return {
                "type": "dockerfile",
                "image": None,
                "install_cmd": None,
                "build_cmd": None,
            }

        # Find matching strategy by primary language
        for lang_name, _ in sorted_langs:
            if lang_name in BUILD_STRATEGIES:
                strategy = BUILD_STRATEGIES[lang_name].copy()
                strategy["type"] = "language"
                strategy["language"] = lang_name
                return strategy

        return None

    async def build_in_docker(
        self, owner: str, repo: str, languages: Dict, detected_files: list
    ) -> Dict[str, Any]:
        """
        Attempt to build a repository in a Docker sandbox.
        
        Steps:
        1. Determine build strategy
        2. Create container with appropriate base image
        3. Clone repository
        4. Install dependencies
        5. Run build command
        6. Capture results
        """
        strategy = self._get_strategy(languages, detected_files)
        if not strategy:
            return {
                "build_status": "skipped",
                "build_logs": "No build strategy available for detected languages",
                "build_duration_seconds": 0,
            }

        if not self.docker_available:
            return await self.rule_based_analysis(
                owner, repo, languages, detected_files, strategy
            )

        if strategy.get("type") == "dockerfile":
            return await self.rule_based_analysis(
                owner, repo, languages, detected_files, strategy
            )

        start_time = time.time()
        logs = []

        try:
            repo_url = f"https://github.com/{owner}/{repo}.git"
            image = strategy["image"]

            # Build the combined command
            commands = [
                "apt-get update -qq && apt-get install -y -qq git > /dev/null 2>&1 || apk add --no-cache git > /dev/null 2>&1 || true",
                f"git clone --depth 1 {repo_url} /workspace",
                "cd /workspace",
            ]

            if strategy["install_cmd"]:
                commands.append(f"cd /workspace && {strategy['install_cmd']}")

            if strategy["build_cmd"]:
                commands.append(f"cd /workspace && {strategy['build_cmd']}")

            full_command = " && ".join(commands)

            logger.info(f"Building {owner}/{repo} with image {image}")
            logs.append(f"[INFO] Using image: {image}")
            logs.append(f"[INFO] Strategy: {strategy.get('language', 'dockerfile')}")

            # Run container
            container = self.docker_client.containers.run(
                image=image,
                command=["sh", "-c", full_command],
                detach=True,
                mem_limit="512m",
                cpu_period=100000,
                cpu_quota=50000,  # 50% CPU
                network_mode="bridge",
                remove=False,
            )

            # Wait for completion with timeout
            result = container.wait(timeout=settings.DOCKER_TIMEOUT)
            exit_code = result.get("StatusCode", -1)

            # Get container logs
            container_logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            logs.append(container_logs)

            # Cleanup
            try:
                container.remove(force=True)
            except Exception:
                pass

            duration = time.time() - start_time

            if exit_code == 0:
                build_status = "success"
                logs.append(f"\n[SUCCESS] Build completed in {duration:.1f}s")
            else:
                build_status = "failed"
                logs.append(f"\n[FAILED] Build failed with exit code {exit_code}")

            return {
                "build_status": build_status,
                "build_logs": "\n".join(logs),
                "build_duration_seconds": round(duration, 2),
                "exit_code": exit_code,
            }

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            if "timeout" in error_msg.lower() or "read timed out" in error_msg.lower():
                build_status = "timeout"
            else:
                build_status = "failed"

            logs.append(f"\n[ERROR] {error_msg}")

            # Try cleanup
            try:
                if 'container' in locals():
                    container.stop(timeout=5)
                    container.remove(force=True)
            except Exception:
                pass

            return {
                "build_status": build_status,
                "build_logs": "\n".join(logs),
                "build_duration_seconds": round(duration, 2),
            }

    async def rule_based_analysis(
        self, owner: str, repo: str, languages: Dict,
        detected_files: list, strategy: Dict
    ) -> Dict[str, Any]:
        """
        Fallback: Rule-based static analysis when Docker is not available.
        Checks for common build issues without actually running the build.
        """
        logs = ["[INFO] Docker not available — performing rule-based analysis"]
        issues = []

        # Check if dependency file exists
        dep_file = strategy.get("dep_file", "")
        if dep_file and dep_file not in detected_files:
            alt_files = strategy.get("alt_dep_files", [])
            if not any(f in detected_files for f in alt_files):
                issues.append(f"Missing dependency file: {dep_file}")

        # Check for Dockerfile
        if "Dockerfile" not in detected_files:
            issues.append("No Dockerfile found")

        # Check for CI/CD
        ci_files = [".github/workflows", ".gitlab-ci.yml", ".travis.yml", "Jenkinsfile"]
        if not any(f in detected_files for f in ci_files):
            issues.append("No CI/CD configuration found")

        # Check for README
        readme_files = ["README.md", "README.rst", "README.txt", "README"]
        has_readme = any(f.lower().startswith("readme") for f in detected_files)
        if not has_readme:
            issues.append("No README file found")

        if issues:
            build_status = "failed"
            logs.append(f"\n[WARNING] Found {len(issues)} potential issues:")
            for issue in issues:
                logs.append(f"  - {issue}")
        else:
            build_status = "success"
            logs.append("\n[OK] No obvious build issues detected (static analysis only)")

        return {
            "build_status": build_status,
            "build_logs": "\n".join(logs),
            "build_duration_seconds": 0,
            "rule_based": True,
            "issues": issues,
        }
