"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ── Enums ──────────────────────────────────────────────

class BatchStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RepoStatusEnum(str, Enum):
    QUEUED = "queued"
    SCRAPING = "scraping"
    ANALYZING = "analyzing"
    BUILDING = "building"
    COMPLETED = "completed"
    FAILED = "failed"


class FeasibilityClassEnum(str, Enum):
    BUILDABLE = "buildable"
    BUILDABLE_WITH_FIXES = "buildable_with_fixes"
    NOT_BUILDABLE = "not_buildable"


# ── Upload ──────────────────────────────────────────────

class UploadResponse(BaseModel):
    batch_id: UUID
    filename: str
    total_repos: int
    repositories: List[str]
    message: str


class BatchStatusResponse(BaseModel):
    id: UUID
    filename: str
    total_repos: int
    processed_count: int
    status: BatchStatusEnum
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Repository ──────────────────────────────────────────

class RepositoryBase(BaseModel):
    url: str
    owner: str
    name: str


class RepositoryResponse(BaseModel):
    id: UUID
    url: str
    owner: str
    name: str
    description: Optional[str] = None
    stars: int = 0
    forks: int = 0
    status: RepoStatusEnum
    batch_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RepositoryListResponse(BaseModel):
    total: int
    repositories: List[RepositoryResponse]


# ── Analysis ──────────────────────────────────────────────

class RecommendationResponse(BaseModel):
    id: UUID
    category: str
    severity: str
    title: str
    description: str
    fix: str
    effort: str
    estimated_time: Optional[str] = None
    ai_provider: str

    model_config = {"from_attributes": True}


class AnalysisResultResponse(BaseModel):
    id: UUID
    repo_id: UUID
    languages: Dict[str, Any] = {}
    frameworks: List[str] = []
    dependencies: Dict[str, Any] = {}
    tech_layers: Dict[str, Any] = {}
    detected_files: List[str] = []
    readme_summary: Optional[str] = None
    build_status: str = "pending"
    build_logs: Optional[str] = None
    build_duration_seconds: Optional[float] = None
    feasibility_score: float = 0.0
    feasibility_class: Optional[FeasibilityClassEnum] = None
    score_breakdown: Dict[str, Any] = {}
    security_score: Optional[float] = None
    recommendations: List[RecommendationResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class RepositoryDetailResponse(BaseModel):
    repository: RepositoryResponse
    analysis: Optional[AnalysisResultResponse] = None


class AnalyzeRequest(BaseModel):
    url: Optional[str] = None  # For single URL analysis


class AnalysisStatusResponse(BaseModel):
    repo_id: UUID
    status: RepoStatusEnum
    message: str


# ── Dashboard ──────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_repos: int = 0
    buildable: int = 0
    buildable_with_fixes: int = 0
    not_buildable: int = 0
    in_progress: int = 0
    total_batches: int = 0
    avg_feasibility_score: float = 0.0


class TechDistributionItem(BaseModel):
    name: str
    count: int
    percentage: float


class TechDistributionResponse(BaseModel):
    languages: List[TechDistributionItem] = []
    frameworks: List[TechDistributionItem] = []


class FeasibilityOverviewResponse(BaseModel):
    buildable: int = 0
    buildable_with_fixes: int = 0
    not_buildable: int = 0
    pending: int = 0
    score_distribution: List[Dict[str, Any]] = []  # [{range: "0-20", count: 5}, ...]


class RecentActivityItem(BaseModel):
    repo_name: str
    repo_url: str
    status: str
    feasibility_class: Optional[str] = None
    feasibility_score: Optional[float] = None
    timestamp: datetime


class DashboardResponse(BaseModel):
    stats: DashboardStats
    tech_distribution: TechDistributionResponse
    feasibility_overview: FeasibilityOverviewResponse
    recent_activity: List[RecentActivityItem] = []
