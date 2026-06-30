"""
AI Recommendation Engine — Uses OpenRouter API (primary) with Gemini optional fallback
to generate smart, contextual fix recommendations for repository build issues.
Includes automatic retry with exponential backoff and model fallback chain.
"""
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# ── Model fallback chain (tried in order if rate-limited) ──
FALLBACK_MODELS = [
    "deepseek/deepseek-v4-flash:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-coder:free",
    "google/gemma-4-31b-it:free",
]

# ── Retry settings ──
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds


def _to_recommendation_dict(item: Any) -> Optional[Dict[str, Any]]:
    """Normalize various LLM response item shapes into a recommendation dict."""
    if isinstance(item, dict):
        return item

    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        # String-only recommendation from model; map to a minimal actionable format.
        return {
            "category": "build",
            "severity": "medium",
            "title": text[:120],
            "description": text,
            "fix": text,
            "effort": "medium",
            "estimated_time": "",
        }

    return None


@dataclass
class RecommendationItem:
    """A single fix recommendation."""
    category: str           # dependency, config, build, ci_cd, documentation, security
    severity: str           # critical, high, medium, low
    title: str
    description: str
    fix: str                # Specific fix command or action
    effort: str = "medium"  # low, medium, high
    estimated_time: str = ""
    ai_provider: str = "openrouter"


@dataclass
class AnalysisContext:
    """Context data sent to the AI for analysis."""
    repo_name: str = ""
    repo_url: str = ""
    languages: Dict[str, Any] = field(default_factory=dict)
    frameworks: List[str] = field(default_factory=list)
    dependencies: Dict[str, Any] = field(default_factory=dict)
    detected_files: List[str] = field(default_factory=list)
    build_status: str = ""
    build_logs: str = ""
    readme_summary: str = ""
    missing_elements: List[str] = field(default_factory=list)
    feasibility_score: float = 0.0


# ── System Prompt ──────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior DevOps engineer and software architect. Your job is to analyze 
GitHub repositories for build feasibility, and to perform security scanning on their dependencies.

You MUST respond with valid JSON only. No markdown, no explanation outside JSON.

CRITICAL SECURITY TASK:
Scan the provided dependencies JSON. If you find known vulnerable, outdated, or deprecated packages 
(e.g., old versions of express, requests, django, log4j, etc.), you MUST create a recommendation 
with "category": "security".

Response format:
{
  "recommendations": [
    {
      "category": "dependency|config|build|ci_cd|documentation|security",
      "severity": "critical|high|medium|low",
      "title": "Short title of the issue",
      "description": "Detailed explanation of the problem",
      "fix": "Specific command or action to fix this",
      "effort": "low|medium|high",
      "estimated_time": "e.g. 5 minutes, 1 hour, 2 hours"
    }
  ],
  "overall_assessment": "Brief overall assessment of the repository",
  "build_probability": 0-100
}"""


def _build_analysis_prompt(context: AnalysisContext) -> str:
    """Build the analysis prompt from context data."""

    # Identify missing elements
    missing = []
    dep_files = [
        "requirements.txt", "package.json", "pom.xml", "build.gradle",
        "go.mod", "Cargo.toml", "Gemfile", "pyproject.toml"
    ]
    has_any_dep = any(f in context.detected_files for f in dep_files)
    if not has_any_dep:
        missing.append("No dependency management file found")

    if "Dockerfile" not in context.detected_files:
        missing.append("No Dockerfile found")

    ci_files = [".github/workflows", ".gitlab-ci.yml", ".travis.yml", "Jenkinsfile"]
    if not any(f in context.detected_files for f in ci_files):
        missing.append("No CI/CD pipeline configuration")

    if not context.readme_summary:
        missing.append("No README or documentation")

    # Build prompt
    prompt = f"""Analyze this GitHub repository for build feasibility and provide fix recommendations.

## Repository Information
- **Name**: {context.repo_name}
- **URL**: {context.repo_url}
- **Languages**: {json.dumps(context.languages)}
- **Frameworks**: {', '.join(context.frameworks) if context.frameworks else 'None detected'}
- **Detected Files**: {', '.join(context.detected_files) if context.detected_files else 'None'}
- **Feasibility Score**: {context.feasibility_score}/100

## Build Result
- **Status**: {context.build_status}
- **Build Logs**:
```
{context.build_logs[:3000] if context.build_logs else 'No build logs available'}
```

## Missing Elements
{chr(10).join(f'- {m}' for m in missing) if missing else '- None identified'}

## Dependencies
{json.dumps(context.dependencies, indent=2)[:2000]}

Provide specific, actionable recommendations to make this repository buildable.
Focus on the most critical issues first. Include exact commands and file changes needed.
Respond with valid JSON only."""

    return prompt


def _clean_json_text(text: str) -> str:
    """Strip markdown code fences and whitespace from LLM response."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    # Handle ```json prefix
    if text.startswith("json"):
        text = text[4:].strip()
    return text


async def _openrouter_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.3,
    timeout: float = 120.0,
) -> str:
    """
    Send a chat completion to OpenRouter with automatic retry + model fallback.
    Returns the raw content string from the response.
    Raises on total failure after all retries and fallbacks.
    """
    primary_model = model or settings.OPENROUTER_MODEL

    # Build ordered model list: primary first, then fallbacks (deduped)
    models_to_try = [primary_model]
    for fb in FALLBACK_MODELS:
        if fb not in models_to_try:
            models_to_try.append(fb)

    last_error = None

    for current_model in models_to_try:
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://autodev-intelligence.app",
                            "X-Title": "AutoDev Intelligence",
                        },
                        json={
                            "model": current_model,
                            "messages": messages,
                            "temperature": temperature,
                        },
                    )

                    # Success
                    if response.status_code == 200:
                        result = response.json()
                        content = result["choices"][0]["message"]["content"]
                        logger.info(f"OpenRouter success with {current_model} (attempt {attempt + 1})")
                        return content

                    # Rate limited — retry with backoff
                    if response.status_code == 429:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            f"Rate limited on {current_model} (attempt {attempt + 1}/{MAX_RETRIES}), "
                            f"retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                        continue

                    # Other HTTP error — don't retry, try next model
                    response.raise_for_status()

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(f"{current_model} HTTP error {e.response.status_code}, trying next model...")
                break  # Move to next model
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(f"{current_model} timed out (attempt {attempt + 1}), retrying...")
                continue
            except Exception as e:
                last_error = e
                logger.warning(f"{current_model} unexpected error: {e}")
                break  # Move to next model

        logger.warning(f"All retries exhausted for {current_model}, trying next fallback...")

    raise RuntimeError(f"All OpenRouter models failed. Last error: {last_error}")


class AIRecommender:
    """
    Multi-provider AI recommendation engine.
    Primary: OpenRouter API (cloud-hosted models) with retry + fallback chain
    Optional: Gemini when explicitly configured
    Final fallback: rule-based recommendations
    """

    def __init__(self):
        self.provider = settings.AI_PROVIDER
        self.gemini_client = None
        self.openrouter_available = False
        self._init_providers()

    def _init_providers(self):
        """Initialize AI providers."""
        # Initialize Gemini only when explicitly enabled.
        if self.provider == "gemini" and settings.GEMINI_API_KEY:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
                logger.info("Gemini AI client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}")

        # Check OpenRouter availability
        if settings.OPENROUTER_API_KEY:
            self.openrouter_available = True
            logger.info(f"OpenRouter configured with model: {settings.OPENROUTER_MODEL}")
        else:
            logger.warning("OPENROUTER_API_KEY not set — OpenRouter unavailable")

    async def get_recommendations(self, context: AnalysisContext) -> List[RecommendationItem]:
        """
        Get AI-powered fix recommendations.
        Uses provider-specific strategy with rule-based final fallback.
        """
        prompt = _build_analysis_prompt(context)

        # Gemini mode (explicit only)
        if self.provider == "gemini" and self.gemini_client:
            try:
                result = await self._query_gemini(prompt)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Gemini failed, trying fallback: {e}")

        # OpenRouter (primary for all non-gemini providers, and fallback for gemini)
        if self.openrouter_available:
            try:
                result = await self._query_openrouter(prompt)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"OpenRouter failed: {e}")

        # Final fallback: rule-based recommendations
        logger.info("All AI providers failed, using rule-based recommendations")
        return self._rule_based_recommendations(context)

    async def _query_gemini(self, prompt: str) -> List[RecommendationItem]:
        """Query Google Gemini API for recommendations."""
        try:
            response = self.gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n" + prompt}]}
                ],
            )

            text = _clean_json_text(response.text)
            data = json.loads(text)
            return self._parse_ai_response(data, "gemini")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON response: {e}")
            return []
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    async def _query_openrouter(self, prompt: str) -> List[RecommendationItem]:
        """Query OpenRouter API for recommendations with retry + fallback."""
        try:
            content = await _openrouter_chat(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                timeout=120.0,
            )

            text = _clean_json_text(content)
            data = json.loads(text)
            return self._parse_ai_response(data, "openrouter")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenRouter JSON response: {e}")
            return []
        except Exception as e:
            logger.error(f"OpenRouter API error: {e}")
            raise

    def _parse_ai_response(self, data: Dict, provider: str) -> List[RecommendationItem]:
        """Parse the AI JSON response into RecommendationItem objects."""
        recommendations = []

        raw_items: Any = []
        if isinstance(data, dict):
            if "recommendations" in data:
                raw_items = data.get("recommendations", [])
            elif "data" in data and isinstance(data.get("data"), dict):
                raw_items = data["data"].get("recommendations", [])
            else:
                # Single-object fallback: treat entire dict as one recommendation candidate.
                raw_items = [data]
        elif isinstance(data, list):
            raw_items = data

        # Some models return recommendation map objects instead of arrays.
        if isinstance(raw_items, dict):
            raw_items = list(raw_items.values())

        for raw in raw_items or []:
            try:
                rec = _to_recommendation_dict(raw)
                if not rec:
                    continue

                item = RecommendationItem(
                    category=rec.get("category", "build"),
                    severity=rec.get("severity", "medium"),
                    title=rec.get("title", "Unknown issue"),
                    description=rec.get("description", ""),
                    fix=rec.get("fix", ""),
                    effort=rec.get("effort", "medium"),
                    estimated_time=rec.get("estimated_time", ""),
                    ai_provider=provider,
                )
                recommendations.append(item)
            except Exception as e:
                logger.warning(f"Failed to parse recommendation: {e}")
                continue

        return recommendations

    def _rule_based_recommendations(self, context: AnalysisContext) -> List[RecommendationItem]:
        """Fallback: Generate recommendations using rule-based analysis."""
        recs = []

        # Check for dependency files
        dep_files = {
            "Python": ["requirements.txt", "pyproject.toml", "setup.py"],
            "JavaScript": ["package.json"],
            "Java": ["pom.xml", "build.gradle"],
            "Go": ["go.mod"],
            "Rust": ["Cargo.toml"],
            "Ruby": ["Gemfile"],
        }

        for lang in context.languages:
            if lang in dep_files:
                if not any(f in context.detected_files for f in dep_files[lang]):
                    recs.append(RecommendationItem(
                        category="dependency",
                        severity="critical",
                        title=f"Missing dependency file for {lang}",
                        description=f"No dependency management file found for {lang}. This prevents automated dependency installation.",
                        fix=f"Create a {dep_files[lang][0]} file listing all project dependencies.",
                        effort="medium",
                        estimated_time="15-30 minutes",
                        ai_provider="rule_based",
                    ))

        # Check for Dockerfile
        if "Dockerfile" not in context.detected_files:
            recs.append(RecommendationItem(
                category="config",
                severity="medium",
                title="No Dockerfile found",
                description="The repository lacks a Dockerfile for containerization. This makes reproducible builds harder.",
                fix="Add a Dockerfile with the appropriate base image and build instructions.",
                effort="medium",
                estimated_time="30 minutes - 1 hour",
                ai_provider="rule_based",
            ))

        # Check for CI/CD
        ci_files = [".github/workflows", ".gitlab-ci.yml", ".travis.yml"]
        if not any(f in context.detected_files for f in ci_files):
            recs.append(RecommendationItem(
                category="ci_cd",
                severity="low",
                title="No CI/CD pipeline configured",
                description="No continuous integration/deployment configuration found.",
                fix="Add a .github/workflows/ci.yml file with build and test steps.",
                effort="medium",
                estimated_time="30 minutes",
                ai_provider="rule_based",
            ))

        # Check README
        if not context.readme_summary:
            recs.append(RecommendationItem(
                category="documentation",
                severity="medium",
                title="Missing or empty README",
                description="The repository has no README file or it is empty. Documentation is essential for reproducibility.",
                fix="Create a README.md with installation instructions, usage examples, and build steps.",
                effort="low",
                estimated_time="15-30 minutes",
                ai_provider="rule_based",
            ))

        # Check build errors
        if context.build_status == "failed" and context.build_logs:
            logs_lower = context.build_logs.lower()
            if "modulenotfounderror" in logs_lower or "no module named" in logs_lower:
                recs.append(RecommendationItem(
                    category="dependency",
                    severity="critical",
                    title="Missing Python module dependency",
                    description="A required Python module is not listed in dependencies.",
                    fix="Add the missing module to requirements.txt and run 'pip install -r requirements.txt'.",
                    effort="low",
                    estimated_time="5-10 minutes",
                    ai_provider="rule_based",
                ))
            if "npm err" in logs_lower or "enoent" in logs_lower:
                recs.append(RecommendationItem(
                    category="dependency",
                    severity="critical",
                    title="npm dependency installation failed",
                    description="Node.js dependency installation encountered errors.",
                    fix="Run 'npm install' locally and fix any peer dependency conflicts. Update package.json.",
                    effort="medium",
                    estimated_time="15-30 minutes",
                    ai_provider="rule_based",
                ))

        return recs
