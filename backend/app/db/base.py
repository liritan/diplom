from app.db.base_class import Base

# Import all models here for Alembic/Migrations to see them
from app.models.user import User
from app.models.content import Test, Question, UserTestResult, CaseSolution
from app.models.profile import SoftSkillsProfile, DevelopmentPlan, ProfileHistory
from app.models.analysis import AnalysisTask, AnalysisResult
from app.models.chat import ChatMessage, ChatAudio
