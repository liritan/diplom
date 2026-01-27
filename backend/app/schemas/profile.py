from typing import List
from pydantic import BaseModel
from datetime import datetime


class ProfileHistory(BaseModel):
    """Schema for profile history snapshot"""
    id: int
    user_id: int
    profile_id: int
    
    # Snapshot of scores at this point in time
    communication_score: float
    emotional_intelligence_score: float
    critical_thinking_score: float
    time_management_score: float
    leadership_score: float
    
    created_at: datetime

    class Config:
        from_attributes = True


class StrengthsWeaknesses(BaseModel):
    """Schema for identified strengths and weaknesses"""
    strengths: List[str]  # Top-3 skills with highest scores
    weaknesses: List[str]  # Top-3 skills with lowest scores


class ProfileWithHistory(BaseModel):
    """Schema for profile with historical data"""
    current: dict  # Current skill scores
    history: List[ProfileHistory]
    strengths: List[str]
    weaknesses: List[str]
