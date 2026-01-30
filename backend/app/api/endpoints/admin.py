from typing import Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.models.profile import SoftSkillsProfile, DevelopmentPlan
from app.models.analysis import AnalysisResult
from app.models.content import Test, Question, UserTestResult, CaseSolution
from app.schemas.user import User as UserSchema
from app.schemas.analysis import AnalysisResult as AnalysisResultSchema
from app.schemas.content import (
    Test as TestSchema,
    TestCreate,
    TestUpdate,
    Question as QuestionSchema,
    QuestionCreate,
    QuestionUpdate,
    UserTestResult as UserTestResultSchema,
    CaseSolution as CaseSolutionSchema,
    SoftSkillsProfile as SoftSkillsProfileSchema,
)
from app.schemas.plan import (
    DevelopmentPlan as DevelopmentPlanSchema,
    MaterialItem,
    MaterialUpdate,
    TaskItem,
    TaskUpdate,
)

router = APIRouter()


def _ensure_plan_content(content: Optional[dict]) -> dict:
    base = {
        "weaknesses": [],
        "materials": [],
        "tasks": [],
        "recommended_tests": [],
    }
    if not isinstance(content, dict):
        return base
    for key, default_value in base.items():
        content.setdefault(key, default_value)
    return content


async def _get_active_plan(user_id: int, db: AsyncSession) -> DevelopmentPlan:
    result = await db.execute(
        select(DevelopmentPlan)
        .where(
            (DevelopmentPlan.user_id == user_id)
            & (DevelopmentPlan.is_archived == False)
        )
        .order_by(DevelopmentPlan.generated_at.desc())
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Активный план развития не найден")
    return plan


class RetryResponse(BaseModel):
    """Response for retry operation"""
    message: str
    status: str


class AdminUserStats(BaseModel):
    user: UserSchema
    analysis_count: int
    test_results_count: int
    case_solutions_count: int


class SetUserPasswordPayload(BaseModel):
    new_password: str


@router.post("/retry-failed", response_model=RetryResponse)
async def retry_failed_analyses(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Manually trigger retry of all failed analysis tasks.
    
    Admin only endpoint that:
    - Finds all tasks with status="failed" and retry_count < 3
    - Retries processing them in background
    
    Requirements: 6.2
    """
    from app.tasks.background_tasks import retry_failed_analyses_background
    
    # Trigger background task to retry failed analyses
    background_tasks.add_task(retry_failed_analyses_background)
    
    return RetryResponse(
        message="Повторная обработка неудачных анализов запущена в фоновом режиме",
        status="processing"
    )


@router.get("/users", response_model=list[AdminUserStats])
async def admin_list_users(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    users_result = await db.execute(select(User).order_by(User.id.asc()).limit(limit))
    users = list(users_result.scalars().all())

    analysis_counts_result = await db.execute(
        select(AnalysisResult.user_id, func.count(AnalysisResult.id))
        .group_by(AnalysisResult.user_id)
    )
    analysis_counts = {row[0]: int(row[1]) for row in analysis_counts_result.all()}

    test_counts_result = await db.execute(
        select(UserTestResult.user_id, func.count(UserTestResult.id))
        .group_by(UserTestResult.user_id)
    )
    test_counts = {row[0]: int(row[1]) for row in test_counts_result.all()}

    case_counts_result = await db.execute(
        select(CaseSolution.user_id, func.count(CaseSolution.id))
        .group_by(CaseSolution.user_id)
    )
    case_counts = {row[0]: int(row[1]) for row in case_counts_result.all()}

    return [
        AdminUserStats(
            user=u,
            analysis_count=analysis_counts.get(u.id, 0),
            test_results_count=test_counts.get(u.id, 0),
            case_solutions_count=case_counts.get(u.id, 0),
        )
        for u in users
    ]


@router.get("/users/{user_id}", response_model=UserSchema)
async def admin_get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/users/{user_id}/password", response_model=dict)
async def admin_set_user_password(
    user_id: int,
    payload: SetUserPasswordPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from app.core import security
    user.hashed_password = security.get_password_hash(payload.new_password)
    db.add(user)
    await db.commit()
    return {"status": "ok"}


@router.get("/users/{user_id}/profile", response_model=Optional[SoftSkillsProfileSchema])
async def admin_get_user_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    result = await db.execute(select(SoftSkillsProfile).where(SoftSkillsProfile.user_id == user_id))
    profile = result.scalars().first()
    return profile


@router.get("/users/{user_id}/analysis", response_model=list[AnalysisResultSchema])
async def admin_get_user_analysis_results(
    user_id: int,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    result = await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.user_id == user_id)
        .order_by(AnalysisResult.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.delete("/users/{user_id}/test-results")
async def admin_delete_user_test_results(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    result = await db.execute(
        delete(UserTestResult).where(UserTestResult.user_id == user_id)
    )
    await db.commit()
    return {"status": "deleted", "deleted": int(result.rowcount or 0)}


@router.delete("/seed/tests")
async def admin_delete_seed_tests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    seed_titles = [
        "Тест: основы коммуникации",
        "Кейс: конфликт с коллегой",
        "Тест: тайм-менеджмент",
        "Тест: критическое мышление",
        "Тест: эмоциональный интеллект",
        "Тест: лидерство",
    ]

    tests_res = await db.execute(select(Test.id).where(Test.title.in_(seed_titles)))
    test_ids = [int(r[0]) for r in tests_res.all()]
    if not test_ids:
        return {"status": "ok", "deleted_tests": 0}

    await db.execute(delete(UserTestResult).where(UserTestResult.test_id.in_(test_ids)))
    await db.execute(delete(CaseSolution).where(CaseSolution.test_id.in_(test_ids)))
    await db.execute(delete(Question).where(Question.test_id.in_(test_ids)))
    tests_del = await db.execute(delete(Test).where(Test.id.in_(test_ids)))
    await db.commit()

    return {"status": "deleted", "deleted_tests": int(tests_del.rowcount or 0)}


@router.get("/users/{user_id}/tests", response_model=list[UserTestResultSchema])
async def admin_get_user_test_results(
    user_id: int,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    result = await db.execute(
        select(UserTestResult)
        .where(UserTestResult.user_id == user_id)
        .order_by(UserTestResult.completed_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/users/{user_id}/cases", response_model=list[CaseSolutionSchema])
async def admin_get_user_case_solutions(
    user_id: int,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    result = await db.execute(
        select(CaseSolution)
        .where(CaseSolution.user_id == user_id)
        .order_by(CaseSolution.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/tests", response_model=list[TestSchema])
async def admin_list_tests(
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    result = await db.execute(
        select(Test)
        .options(selectinload(Test.questions))
        .order_by(Test.id.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.post("/tests", response_model=TestSchema)
async def admin_create_test(
    *,
    db: AsyncSession = Depends(get_db),
    test_in: TestCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    test = Test(title=test_in.title, description=test_in.description, type=test_in.type)
    db.add(test)
    await db.commit()
    result = await db.execute(
        select(Test)
        .options(selectinload(Test.questions))
        .where(Test.id == test.id)
    )
    return result.scalars().first()


@router.patch("/tests/{test_id}", response_model=TestSchema)
async def admin_update_test(
    *,
    db: AsyncSession = Depends(get_db),
    test_id: int,
    test_in: TestUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    result = await db.execute(
        select(Test)
        .options(selectinload(Test.questions))
        .where(Test.id == test_id)
    )
    test = result.scalars().first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    if test_in.title is not None:
        test.title = test_in.title
    if test_in.description is not None:
        test.description = test_in.description
    if test_in.type is not None:
        test.type = test_in.type

    await db.commit()
    result = await db.execute(
        select(Test)
        .options(selectinload(Test.questions))
        .where(Test.id == test_id)
    )
    return result.scalars().first()


@router.delete("/tests/{test_id}")
async def admin_delete_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalars().first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    await db.delete(test)
    await db.commit()
    return {"status": "deleted"}


@router.get("/tests/{test_id}/questions", response_model=list[QuestionSchema])
async def admin_list_questions(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    result = await db.execute(select(Question).where(Question.test_id == test_id).order_by(Question.id.asc()))
    return list(result.scalars().all())


@router.post("/tests/{test_id}/questions", response_model=QuestionSchema)
async def admin_create_question(
    *,
    test_id: int,
    db: AsyncSession = Depends(get_db),
    question_in: QuestionCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    q = Question(
        test_id=test_id,
        text=question_in.text,
        type=question_in.type,
        options=question_in.options,
        correct_answer=question_in.correct_answer,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return q


@router.patch("/questions/{question_id}", response_model=QuestionSchema)
async def admin_update_question(
    *,
    question_id: int,
    db: AsyncSession = Depends(get_db),
    question_in: QuestionUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    result = await db.execute(select(Question).where(Question.id == question_id))
    q = result.scalars().first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    if question_in.text is not None:
        q.text = question_in.text
    if question_in.type is not None:
        q.type = question_in.type
    if question_in.options is not None:
        q.options = question_in.options
    if question_in.correct_answer is not None:
        q.correct_answer = question_in.correct_answer

    await db.commit()
    await db.refresh(q)
    return q


@router.delete("/questions/{question_id}")
async def admin_delete_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    result = await db.execute(select(Question).where(Question.id == question_id))
    q = result.scalars().first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    await db.delete(q)
    await db.commit()
    return {"status": "deleted"}


@router.get("/users/{user_id}/plan", response_model=DevelopmentPlanSchema)
async def admin_get_user_plan(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    plan = await _get_active_plan(user_id, db)
    content = _ensure_plan_content(plan.content)
    return DevelopmentPlanSchema(
        id=plan.id,
        user_id=plan.user_id,
        generated_at=plan.generated_at,
        is_archived=plan.is_archived,
        content=jsonable_encoder(content),
    )


@router.post("/users/{user_id}/materials", response_model=MaterialItem)
async def admin_add_material(
    user_id: int,
    material_in: MaterialItem,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    plan = await _get_active_plan(user_id, db)
    content = _ensure_plan_content(plan.content)
    materials = content["materials"]
    if any(str(m.get("id")) == str(material_in.id) for m in materials):
        raise HTTPException(status_code=400, detail="Материал с таким id уже существует")
    material_payload = jsonable_encoder(material_in)
    materials.append(material_payload)
    plan.content = jsonable_encoder(content)
    await db.commit()
    await db.refresh(plan)
    return MaterialItem(**material_payload)


@router.patch("/users/{user_id}/materials/{material_id}", response_model=MaterialItem)
async def admin_update_material(
    user_id: int,
    material_id: str,
    material_in: MaterialUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    plan = await _get_active_plan(user_id, db)
    content = _ensure_plan_content(plan.content)
    materials = content["materials"]
    material = next((m for m in materials if str(m.get("id")) == str(material_id)), None)
    if not material:
        raise HTTPException(status_code=404, detail="Материал не найден")
    if material_in.title is not None:
        material["title"] = material_in.title
    if material_in.url is not None:
        material["url"] = material_in.url
    if material_in.type is not None:
        material["type"] = material_in.type
    if material_in.skill is not None:
        material["skill"] = material_in.skill
    if material_in.difficulty is not None:
        material["difficulty"] = material_in.difficulty
    plan.content = jsonable_encoder(content)
    await db.commit()
    await db.refresh(plan)
    return MaterialItem(**material)


@router.delete("/users/{user_id}/materials/{material_id}")
async def admin_delete_material(
    user_id: int,
    material_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    plan = await _get_active_plan(user_id, db)
    content = _ensure_plan_content(plan.content)
    materials = content["materials"]
    index = next((i for i, m in enumerate(materials) if str(m.get("id")) == str(material_id)), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Материал не найден")
    materials.pop(index)
    plan.content = jsonable_encoder(content)
    await db.commit()
    return {"status": "deleted"}


@router.post("/users/{user_id}/tasks", response_model=TaskItem)
async def admin_add_task(
    user_id: int,
    task_in: TaskItem,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    plan = await _get_active_plan(user_id, db)
    content = _ensure_plan_content(plan.content)
    tasks = content["tasks"]
    if any(str(t.get("id")) == str(task_in.id) for t in tasks):
        raise HTTPException(status_code=400, detail="Задание с таким id уже существует")
    task_payload = jsonable_encoder(task_in)
    if task_payload.get("status") == "completed" and not task_payload.get("completed_at"):
        task_payload["completed_at"] = datetime.now(timezone.utc).isoformat()
    tasks.append(task_payload)
    plan.content = jsonable_encoder(content)
    await db.commit()
    await db.refresh(plan)
    return TaskItem(**task_payload)


@router.patch("/users/{user_id}/tasks/{task_id}", response_model=TaskItem)
async def admin_update_task(
    user_id: int,
    task_id: str,
    task_in: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    plan = await _get_active_plan(user_id, db)
    content = _ensure_plan_content(plan.content)
    tasks = content["tasks"]
    task = next((t for t in tasks if str(t.get("id")) == str(task_id)), None)
    if not task:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    if task_in.description is not None:
        task["description"] = task_in.description
    if task_in.skill is not None:
        task["skill"] = task_in.skill
    if task_in.status is not None:
        task["status"] = task_in.status
    if task_in.completed_at is not None:
        task["completed_at"] = task_in.completed_at or None
    if task.get("status") == "completed" and not task.get("completed_at"):
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
    plan.content = jsonable_encoder(content)
    await db.commit()
    await db.refresh(plan)
    return TaskItem(**task)


@router.delete("/users/{user_id}/tasks/{task_id}")
async def admin_delete_task(
    user_id: int,
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    plan = await _get_active_plan(user_id, db)
    content = _ensure_plan_content(plan.content)
    tasks = content["tasks"]
    index = next((i for i, t in enumerate(tasks) if str(t.get("id")) == str(task_id)), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    tasks.pop(index)
    plan.content = jsonable_encoder(content)
    await db.commit()
    return {"status": "deleted"}
