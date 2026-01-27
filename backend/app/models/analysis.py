from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Text, Float, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"
    
    id = Column(String, primary_key=True)  # Task ID (UUID or similar)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    response_type = Column(String, nullable=False)  # 'chat', 'test', 'case'
    response_id = Column(Integer, nullable=False)  # ID of the response
    status = Column(String, nullable=False, default="pending")  # 'pending', 'processing', 'completed', 'failed'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    user = relationship("User", backref="analysis_tasks")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Skill Scores (0-100)
    communication_score = Column(Float, nullable=False)
    emotional_intelligence_score = Column(Float, nullable=False)
    critical_thinking_score = Column(Float, nullable=False)
    time_management_score = Column(Float, nullable=False)
    leadership_score = Column(Float, nullable=False)
    
    # Analysis Details
    strengths = Column(JSON, nullable=True)  # List of identified strengths
    weaknesses = Column(JSON, nullable=True)  # List of identified weaknesses
    feedback = Column(Text, nullable=True)  # Detailed feedback from LLM
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="analysis_results")
    task = relationship("AnalysisTask", backref="result")
