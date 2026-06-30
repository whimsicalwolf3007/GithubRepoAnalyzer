"""
Application configuration using Pydantic BaseSettings.
Reads from environment variables and .env file.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://autodev:autodev@localhost:5432/autodev_db"

    # GitHub
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_API_BASE: str = "https://api.github.com"

    # AI Provider
    AI_PROVIDER: str = "openrouter"  # "openrouter" or "gemini"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "deepseek/deepseek-v4-flash:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Docker
    DOCKER_TIMEOUT: int = 300
    MAX_CONCURRENT_BUILDS: int = 3

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Upload
    UPLOAD_DIR: str = "./uploads"
    REPORTS_DIR: str = "./reports"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
