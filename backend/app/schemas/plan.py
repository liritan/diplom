from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class MaterialItem(BaseModel):
    """Schema for a learning material item"""
    id: str
    title: str
    url: str
    type: str  # 'article', 'video', 'course'
    skill: str  # e.g., 'time_management', 'critical_thinking'
    difficulty: str  # 'beginner', 'intermediate', 'advanced'


class MaterialUpdate(BaseModel):
    """Schema for updating a learning material item"""
    title: Optional[str] = None
    url: Optional[str] = None
    type: Optional[str] = None
    skill: Optional[str] = None
    difficulty: Optional[str] = None


class TaskItem(BaseModel):
    """Schema for a development task item"""
    id: str
    description: str
    skill: str
    status: str = "pending"  # 'pending', 'completed'
    completed_at: Optional[datetime] = None


class TaskUpdate(BaseModel):
    """Schema for updating a development task item"""
    description: Optional[str] = None
    skill: Optional[str] = None
    status: Optional[str] = None
    completed_at: Optional[str] = None


class TestRecommendation(BaseModel):
    """Schema for a recommended test"""
    test_id: int
    title: str
    reason: str


class DevelopmentPlanContent(BaseModel):
    """Schema for development plan content structure"""
    weaknesses: List[str]
    materials: List[MaterialItem]
    tasks: List[TaskItem]
    recommended_tests: List[TestRecommendation]


class DevelopmentPlanBase(BaseModel):
    """Base schema for development plan"""
    content: DevelopmentPlanContent


class DevelopmentPlan(BaseModel):
    """Schema for development plan response"""
    id: int
    user_id: int
    generated_at: datetime
    is_archived: bool = False
    content: dict  # Will contain DevelopmentPlanContent structure

    class Config:
        from_attributes = True


class DevelopmentPlanWithProgress(BaseModel):
    """Schema for development plan with progress tracking"""
    id: int
    user_id: int
    generated_at: datetime
    is_archived: bool
    weaknesses: List[str]
    materials: List[MaterialItem]
    tasks: List[TaskItem]
    recommended_tests: List[TestRecommendation]
    progress: dict  # {"completed": int, "total": int, "percentage": float}
