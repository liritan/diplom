from typing import List, Optional
from pydantic import BaseModel
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


class LibraryMaterialItem(MaterialItem):
    plan_id: int
    plan_generated_at: datetime


class LibraryTaskItem(TaskItem):
    plan_id: int
    plan_generated_at: datetime


class PlanLibraryResponse(BaseModel):
    materials: List[LibraryMaterialItem]
    tasks: List[LibraryTaskItem]


class MaterialProgressItem(BaseModel):
    material_id: str
    linked_test_id: Optional[int] = None
    article_opened: bool = False
    article_opened_at: Optional[datetime] = None
    test_completed: bool = False
    test_completed_at: Optional[datetime] = None
    percentage: float = 0


class BlockAchievementItem(BaseModel):
    id: str
    title: str
    achieved_at: Optional[datetime] = None


class FinalStageProgress(BaseModel):
    final_test_id: Optional[int] = None
    final_simulation_id: Optional[int] = None
    unlocked: bool = False
    final_test_completed: bool = False
    final_simulation_completed: bool = False
    completed: bool = False
    level_up_applied: bool = False
    completed_at: Optional[datetime] = None
    achievement_title: Optional[str] = None


class DevelopmentPlanWithProgress(BaseModel):
    """Schema for development plan with progress tracking"""
    id: int
    user_id: int
    generated_at: datetime
    is_archived: bool
    weaknesses: List[str]
    materials: List[MaterialItem]
    material_progress: List[MaterialProgressItem] = []
    tasks: List[TaskItem]
    recommended_tests: List[TestRecommendation]
    final_stage: Optional[FinalStageProgress] = None
    block_achievements: List[BlockAchievementItem] = []
    progress: dict  # {"completed": int, "total": int, "percentage": float}
