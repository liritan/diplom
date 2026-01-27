from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class SkillScores(BaseModel):
    """Skill scores for all 5 soft skills (0-100)"""
    communication: float = Field(..., ge=0, le=100)
    emotional_intelligence: float = Field(..., ge=0, le=100)
    critical_thinking: float = Field(..., ge=0, le=100)
    time_management: float = Field(..., ge=0, le=100)
    leadership: float = Field(..., ge=0, le=100)
    feedback: Optional[str] = None


class AnalysisTaskCreate(BaseModel):
    """Schema for creating a new analysis task"""
    user_id: int
    response_type: str  # 'chat', 'test', 'case'
    response_id: int


class AnalysisTask(BaseModel):
    """Schema for analysis task response"""
    id: str
    user_id: int
    response_type: str
    response_id: int
    status: str  # 'pending', 'processing', 'completed', 'failed'
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0

    class Config:
        from_attributes = True


class AnalysisResult(BaseModel):
    """Schema for analysis result response"""
    id: int
    task_id: str
    user_id: int
    
    # Skill Scores (0-100)
    communication_score: float
    emotional_intelligence_score: float
    critical_thinking_score: float
    time_management_score: float
    leadership_score: float
    
    # Analysis Details
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None
    feedback: Optional[str] = None
    
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisStatus(BaseModel):
    """Schema for analysis status response"""
    task_id: str
    status: str
    result: Optional[AnalysisResult] = None
