from typing import Any, Optional
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.models.profile import SoftSkillsProfile
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

router = APIRouter()


class RetryResponse(BaseModel):
    """Response for retry operation"""
    message: str
    status: str


class AdminUserStats(BaseModel):
    user: UserSchema
    analysis_count: int
    test_results_count: int
    case_solutions_count: int


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
    result = await db.execute(select(Test).order_by(Test.id.asc()).limit(limit))
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
    await db.refresh(test)
    return test


@router.patch("/tests/{test_id}", response_model=TestSchema)
async def admin_update_test(
    *,
    db: AsyncSession = Depends(get_db),
    test_id: int,
    test_in: TestUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    result = await db.execute(select(Test).where(Test.id == test_id))
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
    await db.refresh(test)
    return test


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
