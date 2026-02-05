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
from app.models.user import User, UserRole
from app.core import security
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
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https://.*\.vercel\.app$|^http://(localhost|127\.0\.0\.1)(:\\d+)?$",
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
            safe_admin_email = settings.DEFAULT_ADMIN_EMAIL

            legacy_admin_email = "admin123@admin.local"
            if safe_admin_email and safe_admin_email != legacy_admin_email:
                legacy_res = await db.execute(select(User).where(User.email == legacy_admin_email))
                legacy_user = legacy_res.scalars().first()
                if legacy_user:
                    safe_res = await db.execute(select(User).where(User.email == safe_admin_email))
                    safe_user = safe_res.scalars().first()
                    if safe_user:
                        legacy_user.email = f"legacy+{legacy_user.id}@{safe_admin_email.split('@')[1]}"
                    else:
                        legacy_user.email = safe_admin_email
                    db.add(legacy_user)
                    await db.commit()

            admin_res = await db.execute(select(func.count(User.id)).where(User.role == UserRole.ADMIN))
            admin_count = int(admin_res.scalar() or 0)
            if admin_count == 0:
                user_res = await db.execute(select(User).where(User.email == safe_admin_email))
                existing = user_res.scalars().first()
                if not existing:
                    db.add(
                        User(
                            email=safe_admin_email,
                            hashed_password=security.get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
                            full_name="Admin",
                            role=UserRole.ADMIN,
                            is_active=True,
                        )
                    )
                    await db.commit()

            seed_demo_tests = os.getenv("SEED_DEMO_TESTS", "0").strip().lower() in {"1", "true", "yes"}
            if seed_demo_tests:
                async def ensure_test(title: str, description: str, type_: str, questions):
                    test_res = await db.execute(select(Test).where(Test.title == title, Test.type == type_))
                    test_obj = test_res.scalars().first()
                    if test_obj:
                        return test_obj

                    test_obj = Test(title=title, description=description, type=type_)
                    db.add(test_obj)
                    await db.flush()

                    for q in questions:
                        db.add(
                            Question(
                                test_id=test_obj.id,
                                text=q.get("text", ""),
                                type=q.get("type", "text"),
                                options=q.get("options"),
                                correct_answer=None,
                            )
                        )

                    return test_obj

                await ensure_test(
                    title="Тест: основы коммуникации",
                    description="Короткий тест для первичной оценки коммуникации и саморефлексии.",
                    type_="quiz",
                    questions=[
                        {"text": "Как вы обычно реагируете на критику?", "type": "text"},
                        {
                            "text": "Что вы делаете, если собеседник вас перебивает?",
                            "type": "multiple_choice",
                            "options": [
                                {"text": "Перебиваю в ответ", "value": 1},
                                {"text": "Спокойно прошу дать договорить", "value": 2},
                                {"text": "Замолкаю и перестаю участвовать", "value": 0},
                            ],
                        },
                    ],
                )

                await ensure_test(
                    title="Кейс: конфликт с коллегой",
                    description="Опишите, как вы бы действовали в конфликтной ситуации в команде.",
                    type_="case",
                    questions=[],
                )

                await ensure_test(
                    title="Тест: тайм-менеджмент",
                    description="Короткий тест про планирование, приоритизацию и дедлайны.",
                    type_="quiz",
                    questions=[{"text": "Как вы обычно планируете задачи на неделю?", "type": "text"}],
                )

                await ensure_test(
                    title="Тест: критическое мышление",
                    description="Проверка навыков анализа информации и аргументации.",
                    type_="quiz",
                    questions=[
                        {"text": "Как вы проверяете достоверность информации перед тем как сделать вывод?", "type": "text"}
                    ],
                )

                await ensure_test(
                    title="Тест: эмоциональный интеллект",
                    description="Саморефлексия и эмпатия в коммуникации.",
                    type_="quiz",
                    questions=[{"text": "Как вы обычно реагируете, когда собеседник раздражён?", "type": "text"}],
                )

                await ensure_test(
                    title="Тест: лидерство",
                    description="Оценка подходов к лидерству и влиянию в команде.",
                    type_="quiz",
                    questions=[
                        {"text": "Как вы распределяете задачи в команде, если сроки поджимают?", "type": "text"}
                    ],
                )

                await db.commit()
        except Exception:
            await db.rollback()

@app.get("/")
async def root():
    return {"message": "Welcome to Soft Skills AI Platform API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from app.db.session import get_db
from app.models.user import User

app = FastAPI()

@app.delete("/delete-test-users")
async def delete_test_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        delete(User).where(User.id.in_([6, 7]))
    )
    await db.commit()
    return {
        "status": "ok",
        "deleted_rows": result.rowcount
    }
