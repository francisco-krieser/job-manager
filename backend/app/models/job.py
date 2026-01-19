from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    DATA_PROCESSING = "data_processing"
    REPORT_GENERATION = "report_generation"
    IMAGE_RESIZE = "image_resize"


class JobRequest(BaseModel):
    job_type: JobType
    metadata: Dict[str, Any] = Field(default_factory=dict)
    max_retries: int = Field(default=3, ge=0, le=10)


class JobResponse(BaseModel):
    job_id: str
    job_type: JobType
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    created_at: int
    updated_at: int
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_code: Optional[str] = None

    class Config:
        from_attributes = True


class ProgressUpdate(BaseModel):
    job_id: str
    status: JobStatus
    progress: int
    message: Optional[str] = None
    timestamp: int
    data: Optional[Dict[str, Any]] = None
