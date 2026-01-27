from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.api.api import api_router
from app.db.session import engine
from app.db.base import Base
from app.db.session import AsyncSessionLocal
from app.models.content import Test, Question
import os

# Initialize structured logging
log_level = os.getenv("LOG_LEVEL", "INFO")
use_json_logging = os.getenv("USE_JSON_LOGGING", "true").lower() == "true"
setup_logging(log_level=log_level, use_json=use_json_logging)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS Configuration
origins = [
    "http://localhost:3000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
async def startup():
    # Warning: This creates tables on startup. 
    # In production, use Alembic migrations.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        try:
            res = await db.execute(select(func.count(Test.id)))
            count = int(res.scalar() or 0)
            if count == 0:
                quiz = Test(
                    title="Тест: основы коммуникации",
                    description="Короткий тест для первичной оценки коммуникации и саморефлексии.",
                    type="quiz",
                )
                db.add(quiz)
                await db.flush()

                db.add_all([
                    Question(
                        test_id=quiz.id,
                        text="Как вы обычно реагируете на критику?",
                        type="text",
                        options=None,
                        correct_answer=None,
                    ),
                    Question(
                        test_id=quiz.id,
                        text="Что вы делаете, если собеседник вас перебивает?",
                        type="multiple_choice",
                        options=[
                            {"text": "Перебиваю в ответ", "value": 1},
                            {"text": "Спокойно прошу дать договорить", "value": 2},
                            {"text": "Замолкаю и перестаю участвовать", "value": 0},
                        ],
                        correct_answer=None,
                    ),
                ])

                case = Test(
                    title="Кейс: конфликт с коллегой",
                    description="Опишите, как вы бы действовали в конфликтной ситуации в команде.",
                    type="case",
                )
                db.add(case)

                await db.commit()
        except Exception:
            await db.rollback()

@app.get("/")
async def root():
    return {"message": "Welcome to Soft Skills AI Platform API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
