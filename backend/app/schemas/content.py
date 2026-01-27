from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

# --- Questions ---
class QuestionBase(BaseModel):
    text: str
    type: str
    options: Optional[List[Dict[str, Any]]] = None

class QuestionCreate(QuestionBase):
    correct_answer: Optional[Dict[str, Any]] = None


class QuestionUpdate(BaseModel):
    text: Optional[str] = None
    type: Optional[str] = None
    options: Optional[List[Dict[str, Any]]] = None
    correct_answer: Optional[Dict[str, Any]] = None

class Question(QuestionBase):
    id: int
    test_id: int

    class Config:
        from_attributes = True


# --- Case Solutions (Cases/Simulations) ---
class CaseSolutionBase(BaseModel):
    test_id: int
    solution: str


class CaseSolutionCreate(BaseModel):
    solution: str


class CaseSolution(CaseSolutionBase):
    id: int
    user_id: int
    analysis_task_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SimulationSubmit(BaseModel):
    conversation: str


class SimulationChatMessage(BaseModel):
    role: str
    text: str


class SimulationReplyRequest(BaseModel):
    messages: List[SimulationChatMessage]

# --- Tests ---
class TestBase(BaseModel):
    title: str
    description: str
    type: str

class TestCreate(TestBase):
    pass


class TestUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None

class Test(TestBase):
    id: int
    created_at: datetime
    questions: List[Question] = []

    class Config:
        from_attributes = True

# --- Results ---
class UserTestResultBase(BaseModel):
    test_id: int
    answers: Dict[str, Any] # q_id: answer


class UserTestSubmit(BaseModel):
    answers: Dict[str, Any]  # q_id: answer


class UserTestResultCreate(UserTestResultBase):
    pass

class UserTestResult(UserTestResultBase):
    id: int
    user_id: int
    score: Optional[float]
    ai_analysis: Optional[str]
    completed_at: datetime

    class Config:
        from_attributes = True

# --- Profile ---
class SoftSkillsProfileBase(BaseModel):
    communication_score: float
    emotional_intelligence_score: float
    critical_thinking_score: float
    time_management_score: float
    leadership_score: float

class SoftSkillsProfile(SoftSkillsProfileBase):
    id: int
    user_id: int
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Plan ---
class DevelopmentPlanBase(BaseModel):
    content: Dict[str, Any]

class DevelopmentPlan(DevelopmentPlanBase):
    id: int
    user_id: int
    generated_at: datetime

    class Config:
        from_attributes = True
