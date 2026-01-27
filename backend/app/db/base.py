from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Import all models here for Alembic/Migrations to see them
from app.models.user import User
from app.models.content import Test, Question, UserTestResult, CaseSolution
from app.models.profile import SoftSkillsProfile, DevelopmentPlan, ProfileHistory
from app.models.analysis import AnalysisTask, AnalysisResult
from app.models.chat import ChatMessage, ChatAudio
