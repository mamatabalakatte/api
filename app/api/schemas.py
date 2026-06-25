from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class InteractionCreate(BaseModel):
    user_id: int = Field(..., description="ID of the user interacting with content")
    content_id: int = Field(..., description="ID of the content item")
    interaction_type: str = Field(..., description="Type of interaction: click, bookmark, like, complete")
    rating: Optional[float] = Field(None, description="Optional rating (e.g. 1.0 to 5.0)")

    @field_validator("interaction_type")
    def validate_type(cls, v):
        allowed = ["click", "bookmark", "like", "complete"]
        if v not in allowed:
            raise ValueError(f"interaction_type must be one of {allowed}")
        return v

    @field_validator("rating")
    def validate_rating(cls, v):
        if v is not None and (v < 1.0 or v > 5.0):
            raise ValueError("rating must be between 1.0 and 5.0")
        return v

class ContentSchema(BaseModel):
    id: int
    title: str
    type: str
    description: Optional[str] = None
    skills: List[str]

class RecommendationItem(BaseModel):
    content: ContentSchema
    score: float
    explanation: str
    method: str
    cached: bool

class HealthResponse(BaseModel):
    status: str
    database_connected: bool
    timestamp: str

class MetricsResponse(BaseModel):
    precision_at_5: float
    recall_at_5: float
    ndcg_at_5: float
    evaluated_users: int
    total_users: int
    total_contents: int
    avg_latency_ms: float
    status: str
