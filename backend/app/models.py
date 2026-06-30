"""
SQLAlchemy database models for AutoDev Intelligence.
Uses PostgreSQL JSONB columns for flexible structured data.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class BatchStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RepoStatus(str, enum.Enum):
    QUEUED = "queued"
    SCRAPING = "scraping"
    ANALYZING = "analyzing"
    BUILDING = "building"
    COMPLETED = "completed"
    FAILED = "failed"


class FeasibilityClass(str, enum.Enum):
    BUILDABLE = "buildable"
    BUILDABLE_WITH_FIXES = "buildable_with_fixes"
    NOT_BUILDABLE = "not_buildable"


class UploadBatch(Base):
    """Represents a batch upload of GitHub repository links from an Excel file."""
    __tablename__ = "upload_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    total_repos = Column(Integer, default=0)
    processed_count = Column(Integer, default=0)
    status = Column(SAEnum(BatchStatus), default=BatchStatus.PENDING)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    repositories = relationship("Repository", back_populates="batch", cascade="all, delete-orphan")


class Repository(Base):
    """Represents a GitHub repository to be analyzed."""
    __tablename__ = "repositories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("upload_batches.id"), nullable=True)
    url = Column(String(500), nullable=False)
    owner = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    stars = Column(Integer, default=0)
    forks = Column(Integer, default=0)
    default_branch = Column(String(100), default="main")
    status = Column(SAEnum(RepoStatus), default=RepoStatus.QUEUED)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    batch = relationship("UploadBatch", back_populates="repositories")
    analysis = relationship("AnalysisResult", back_populates="repository", uselist=False, cascade="all, delete-orphan")


class AnalysisResult(Base):
    """Stores the full analysis result for a repository."""
    __tablename__ = "analysis_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False, unique=True)

    # Tech stack data (JSONB for flexibility)
    languages = Column(JSONB, default=dict)           # {"Python": 45000, "JavaScript": 12000}
    frameworks = Column(JSONB, default=list)           # ["Django", "React"]
    dependencies = Column(JSONB, default=dict)         # {"python": ["django", "requests"], "node": ["react"]}
    tech_layers = Column(JSONB, default=dict)          # {"frontend": {...}, "backend": {...}, "database": {...}, "devops": {...}}
    detected_files = Column(JSONB, default=list)       # ["requirements.txt", "Dockerfile", ...]
    readme_summary = Column(Text, nullable=True)

    # Build results
    build_status = Column(String(50), default="pending")  # success, failed, skipped, timeout
    build_logs = Column(Text, nullable=True)
    build_duration_seconds = Column(Float, nullable=True)

    # Feasibility & Security
    feasibility_score = Column(Float, default=0.0)
    feasibility_class = Column(SAEnum(FeasibilityClass), nullable=True)
    score_breakdown = Column(JSONB, default=dict)      # {"deps": 20, "build_config": 15, ...}
    security_score = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    repository = relationship("Repository", back_populates="analysis")
    recommendations = relationship("Recommendation", back_populates="analysis", cascade="all, delete-orphan")


class Recommendation(Base):
    """AI-generated fix recommendation for a repository."""
    __tablename__ = "recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analysis_results.id"), nullable=False)

    category = Column(String(50), nullable=False)       # dependency, config, build, ci_cd, documentation
    severity = Column(String(20), nullable=False)        # critical, high, medium, low
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    fix = Column(Text, nullable=False)                   # Specific fix command or action
    effort = Column(String(20), default="medium")        # low, medium, high
    estimated_time = Column(String(50), nullable=True)   # "5 minutes", "1 hour"
    ai_provider = Column(String(20), default="gemini")   # gemini, ollama, rule_based

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    analysis = relationship("AnalysisResult", back_populates="recommendations")
