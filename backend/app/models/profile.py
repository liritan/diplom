from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class SoftSkillsProfile(Base):
    __tablename__ = "soft_skills_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    
    # Skills Scores (0-100)
    communication_score = Column(Float, default=0.0)
    emotional_intelligence_score = Column(Float, default=0.0)
    critical_thinking_score = Column(Float, default=0.0)
    time_management_score = Column(Float, default=0.0)
    leadership_score = Column(Float, default=0.0)
    
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    
    user = relationship("User", backref="soft_skills_profile")

class ProfileHistory(Base):
    __tablename__ = "profile_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    profile_id = Column(Integer, ForeignKey("soft_skills_profiles.id"), nullable=False)
    
    # Snapshot of scores at this point in time
    communication_score = Column(Float, nullable=False)
    emotional_intelligence_score = Column(Float, nullable=False)
    critical_thinking_score = Column(Float, nullable=False)
    time_management_score = Column(Float, nullable=False)
    leadership_score = Column(Float, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="profile_history")
    profile = relationship("SoftSkillsProfile", backref="history")


class DevelopmentPlan(Base):
    __tablename__ = "development_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    is_archived = Column(Boolean, default=False, nullable=False)
    
    # JSON structure: 
    # {
    #   "weaknesses": ["Time Management", "Critical Thinking"],
    #   "materials": [
    #     {
    #       "id": "mat_1",
    #       "title": "...",
    #       "url": "...",
    #       "type": "article|video|course",
    #       "skill": "time_management",
    #       "difficulty": "beginner|intermediate|advanced"
    #     }
    #   ],
    #   "tasks": [
    #     {
    #       "id": "task_1",
    #       "description": "...",
    #       "skill": "time_management",
    #       "status": "pending|completed",
    #       "completed_at": null
    #     }
    #   ],
    #   "recommended_tests": [
    #     {
    #       "test_id": 5,
    #       "title": "...",
    #       "reason": "..."
    #     }
    #   ]
    # }
    content = Column(JSON) 
    
    user = relationship("User", backref="development_plans")
