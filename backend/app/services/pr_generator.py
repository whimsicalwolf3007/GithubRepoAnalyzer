"""
PR Generator Service — Automatically creates GitHub Pull Requests for AI recommendations.
Uses OpenRouter API with retry + fallback via the shared _openrouter_chat utility.
"""
import logging
import uuid
import json
from typing import Dict, Any, Tuple
import httpx
from github import Github
from github.GithubException import GithubException
from app.config import settings
from app.engines.ai_recommender import AIRecommender, _openrouter_chat

logger = logging.getLogger(__name__)

class PRGenerator:
    def __init__(self):
        self.github_token = settings.GITHUB_TOKEN
        self.g = Github(self.github_token) if self.github_token else None
        self.ai = AIRecommender()

    async def _generate_file_patch(self, owner: str, repo_name: str, fix_description: str, detected_files: list) -> Tuple[str, str]:
        """
        Use AI to figure out which file to modify and generate the new content.
        """
        # Fetch actual contents of likely files to give AI context
        file_contexts = ""
        repo = self.g.get_repo(f"{owner}/{repo_name}")
        
        # We only check common build files to save context window
        common_files = [f for f in detected_files if any(x in f.lower() for x in ['package.json', 'requirements.txt', 'dockerfile', 'pom.xml', 'go.mod', 'build.gradle'])]
        
        for file_path in common_files:
            try:
                contents = repo.get_contents(file_path)
                file_contexts += f"\n--- {file_path} ---\n{contents.decoded_content.decode('utf-8')}\n"
            except Exception:
                continue

        prompt = f"""
You are an automated pull request generator.
A user wants to apply the following fix to the repository {owner}/{repo_name}:
FIX DESCRIPTION: {fix_description}

Here are the contents of the relevant build files:
{file_contexts}

Your task is to implement the fix.
You MUST respond with valid JSON only.

{{
    "file_path": "exact/path/to/file.ext",
    "new_content": "The complete, exact new content for the file after applying the fix."
}}
"""
        
        # Try Gemini first only when explicitly enabled
        if self.ai.provider == "gemini" and self.ai.gemini_client:
            try:
                response = self.ai.gemini_client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt,
                )
                text = response.text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1]
                    if text.endswith("```"):
                        text = text[:-3]
                data = json.loads(text.strip())
                return data.get("file_path"), data.get("new_content")
            except Exception as e:
                logger.warning(f"Gemini failed to generate patch: {e}")

        # OpenRouter with automatic retry + model fallback
        if settings.OPENROUTER_API_KEY:
            try:
                content = await _openrouter_chat(
                    messages=[
                        {"role": "system", "content": "You are a code patching bot. Output JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    timeout=120.0,
                )

                text = content.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1]
                    if text.endswith("```"):
                        text = text[:-3]
                
                data = json.loads(text.strip())
                return data.get("file_path"), data.get("new_content")
            except Exception as e:
                logger.error(f"OpenRouter failed to generate patch: {e}")

        raise ValueError("AI failed to generate a patch for the PR")

    async def create_auto_fix_pr(self, owner: str, repo_name: str, recommendation: Dict[str, Any], detected_files: list) -> str:
        """
        Creates a Pull Request with the recommended fix.
        Returns the PR URL.
        """
        if not self.g:
            raise ValueError("GITHUB_TOKEN is not configured")

        try:
            # 1. Generate the patch using AI
            fix_description = f"{recommendation['title']}: {recommendation['fix']}"
            file_path, new_content = await self._generate_file_patch(owner, repo_name, fix_description, detected_files)
            
            if not file_path or not new_content:
                raise ValueError("AI failed to determine which file to patch")

            # 2. Get repository
            original_repo = self.g.get_repo(f"{owner}/{repo_name}")
            
            # Check if user owns it, otherwise fork
            current_user = self.g.get_user()
            if original_repo.owner.login == current_user.login:
                repo = original_repo
            else:
                repo = current_user.create_fork(original_repo)
                
            # 3. Create a new branch
            branch_name = f"autodev-fix-{uuid.uuid4().hex[:8]}"
            source_branch = repo.default_branch
            sb = repo.get_branch(source_branch)
            repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=sb.commit.sha)

            # 4. Apply the patch
            commit_message = f"AutoDev Fix: {recommendation['title']}"
            try:
                file_contents = repo.get_contents(file_path, ref=source_branch)
                repo.update_file(
                    path=file_contents.path,
                    message=commit_message,
                    content=new_content,
                    sha=file_contents.sha,
                    branch=branch_name
                )
            except GithubException as e:
                if e.status == 404:
                    # File doesn't exist, so create it
                    repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=new_content,
                        branch=branch_name
                    )
                else:
                    raise

            # 5. Create Pull Request
            pr_title = f"🛠️ AutoDev Fix: {recommendation['title']}"
            pr_body = f"This PR was automatically generated by **AutoDev Intelligence** to resolve the following issue:\n\n" \
                      f"### {recommendation['title']}\n" \
                      f"{recommendation['description']}\n\n" \
                      f"**Fix Applied:** `{recommendation['fix']}`"
                      
            pr = original_repo.create_pull(
                title=pr_title,
                body=pr_body,
                head=f"{repo.owner.login}:{branch_name}",
                base=original_repo.default_branch
            )

            return pr.html_url

        except GithubException as e:
            logger.error(f"GitHub API Error: {e}")
            raise ValueError(f"GitHub API Error: {e.data.get('message', str(e))}")
        except Exception as e:
            logger.error(f"Failed to create PR: {e}")
            raise
