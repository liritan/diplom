from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, JSON, Text, Float, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base

class Test(Base):
    __tablename__ = "tests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    type = Column(String) # 'quiz', 'simulation', 'case'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    questions = relationship("Question", back_populates="test", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"))
    text = Column(Text)
    type = Column(String) # 'multiple_choice', 'scale', 'ranking', 'text', 'voice'
    options = Column(JSON, nullable=True) # For multiple choice: [{"text": "A", "value": 1}]
    correct_answer = Column(JSON, nullable=True) # For automated grading if applicable
    
    test = relationship("Test", back_populates="questions")

class UserTestResult(Base):
    __tablename__ = "user_test_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    test_id = Column(Integer, ForeignKey("tests.id"))
    score = Column(Float, nullable=True)
    details = Column(JSON) # Detailed answers: {"q_id": "answer"}
    ai_analysis = Column(Text, nullable=True) # AI feedback on this specific test
    completed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="test_results")
    test = relationship("Test")

    @property
    def answers(self):
        return self.details or {}


class CaseSolution(Base):
    __tablename__ = "case_solutions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False)
    solution = Column(Text, nullable=False)
    analysis_task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="case_solutions")
    test = relationship("Test")
