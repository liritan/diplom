import asyncio
import json
import logging
import os

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, text
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.api.api import api_router
from app.db.session import engine
from app.db.base import Base
from app.db.session import AsyncSessionLocal
from app.models.content import Test, Question
from app.models.user import User, UserRole
from app.core import security

# Initialize structured logging
log_level = os.getenv("LOG_LEVEL", "INFO")
use_json_logging = os.getenv("USE_JSON_LOGGING", "true").lower() == "true"
setup_logging(log_level=log_level, use_json=use_json_logging)
logger = logging.getLogger(__name__)


def _text_quality_score(value: str) -> int:
    letters = sum(1 for ch in value if ch.isalpha())
    cyrillic = sum(1 for ch in value if ("а" <= ch.lower() <= "я") or ch in {"ё", "Ё"})
    digits = sum(1 for ch in value if ch.isdigit())
    spaces = sum(1 for ch in value if ch.isspace())
    punctuation = sum(1 for ch in value if ch in ".,!?;:()[]{}\"'/-_")
    mojibake_markers = sum(1 for ch in value if ch in "\ufffdÐÑÃÂ")
    control = sum(1 for ch in value if ord(ch) < 32 and ch not in "\r\n\t")
    return letters + (cyrillic * 2) + digits + spaces + punctuation - (mojibake_markers * 6) - (control * 6)


def _repair_text_encoding(value: object) -> str:
    current = str(value or "")
    for _ in range(2):
        improved = None
        for source_encoding in ("cp1251", "latin1"):
            try:
                candidate = current.encode(source_encoding).decode("utf-8")
            except UnicodeError:
                continue
            if candidate == current:
                continue
            if _text_quality_score(candidate) > _text_quality_score(current) + 3:
                improved = candidate
                break
        if improved is None:
            break
        current = improved
    return current


def _repair_payload_encoding(value: object) -> object:
    if isinstance(value, str):
        return _repair_text_encoding(value)
    if isinstance(value, list):
        return [_repair_payload_encoding(item) for item in value]
    if isinstance(value, dict):
        return {key: _repair_payload_encoding(item) for key, item in value.items()}
    return value

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

def _build_cors_origins() -> list[str]:
    default_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    extra = [origin.strip() for origin in str(settings.CORS_ORIGINS or "").split(",") if origin.strip()]
    merged = list(default_origins)
    for origin in extra:
        if origin not in merged:
            merged.append(origin)
    return merged


if settings.CORS_ALLOW_ALL:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_build_cors_origins(),
        allow_origin_regex=(
            r"^https://.*\.(vercel\.app|onrender\.com)$|^http://(localhost|127\.0\.0\.1)(:\\d+)?$"
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def repair_json_encoding_middleware(request: Request, call_next):
    response = await call_next(request)
    content_type = str(response.headers.get("content-type") or "").lower()
    if "application/json" not in content_type:
        return response

    body = b""
    async for chunk in response.body_iterator:
        body += chunk

    if not body:
        return response

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
            background=response.background,
        )

    repaired_payload = _repair_payload_encoding(payload)
    if repaired_payload == payload:
        repaired_body = body
    else:
        repaired_body = json.dumps(repaired_payload, ensure_ascii=False).encode("utf-8")

    headers = dict(response.headers)
    headers.pop("content-length", None)
    return Response(
        content=repaired_body,
        status_code=response.status_code,
        headers=headers,
        media_type="application/json",
        background=response.background,
    )

app.include_router(api_router, prefix=settings.API_V1_STR)


async def _initialize_database() -> None:
    max_retries = max(1, int(settings.DB_STARTUP_MAX_RETRIES))
    retry_delay = max(0.1, float(settings.DB_STARTUP_RETRY_DELAY_SECONDS))

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            if settings.CREATE_TABLES_ON_STARTUP:
                # Safe for existing DB: creates missing tables only.
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
            else:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
            return
        except Exception as exc:  # pragma: no cover - startup operational path
            last_error = exc
            logger.warning(
                "Database startup check failed (attempt %s/%s): %s",
                attempt,
                max_retries,
                exc,
            )
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)

    if last_error is not None:
        raise last_error


@app.on_event("startup")
async def startup():
    await _initialize_database()

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
