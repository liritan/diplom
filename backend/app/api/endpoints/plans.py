from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.models.profile import SoftSkillsProfile, DevelopmentPlan
from app.models.analysis import AnalysisResult
from app.schemas.plan import (
    DevelopmentPlanWithProgress,
    PlanLibraryResponse,
    LibraryMaterialItem,
    LibraryTaskItem,
)
from app.services.plan_service import plan_service
from app.core.config import settings

router = APIRouter()


class TaskCompletionResponse(BaseModel):
    """Response for task completion."""

    task_id: str
    status: str
    completed_at: str
    plan_progress: float


class PlanGenerationResponse(BaseModel):
    """Response for manual plan generation."""

    message: str
    status: str


class MaterialActionResponse(BaseModel):
    material_id: str
    material_percentage: float
    plan_progress: float


@router.get("/me/active", response_model=Optional[DevelopmentPlanWithProgress])
async def get_active_plan(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    try:
        plan = await plan_service.get_active_plan(current_user.id, db)
        if plan is None:
            return None

        profile_row = await db.execute(
            select(SoftSkillsProfile).where(SoftSkillsProfile.user_id == current_user.id)
        )
        profile = profile_row.scalar_one_or_none()
        if profile is not None:
            await plan_service.sanitize_plan_materials_if_needed(plan, profile, db)
            await db.refresh(plan)

        tracking = await plan_service.sync_plan_tracking(
            plan=plan,
            user_id=current_user.id,
            db=db,
            profile=profile,
        )
        await db.refresh(plan)

        content = plan.content if isinstance(plan.content, dict) else {}
        tasks_raw = content.get("tasks", [])
        tasks = tasks_raw if isinstance(tasks_raw, list) else []
        materials_raw = content.get("materials", [])
        materials = materials_raw if isinstance(materials_raw, list) else []

        material_progress_map = tracking.get("material_progress", {})
        if not isinstance(material_progress_map, dict):
            material_progress_map = {}

        material_progress: list[dict[str, Any]] = []
        for material in materials:
            if not isinstance(material, dict):
                continue
            material_id = str(material.get("id", ""))
            row = material_progress_map.get(material_id, {})
            if not isinstance(row, dict):
                row = {}
            material_progress.append(
                {
                    "material_id": material_id,
                    "linked_test_id": row.get("linked_test_id"),
                    "article_opened": bool(row.get("article_opened")),
                    "article_opened_at": row.get("article_opened_at"),
                    "test_completed": bool(row.get("test_completed")),
                    "test_completed_at": row.get("test_completed_at"),
                    "percentage": float(row.get("percentage") or 0),
                }
            )

        return DevelopmentPlanWithProgress(
            id=plan.id,
            user_id=plan.user_id,
            generated_at=plan.generated_at,
            is_archived=plan.is_archived,
            weaknesses=content.get("weaknesses", []),
            materials=materials,
            material_progress=material_progress,
            tasks=tasks,
            recommended_tests=content.get("recommended_tests", []),
            final_stage=tracking.get("final_stage"),
            block_achievements=tracking.get("block_achievements", []),
            progress=tracking.get("progress", {"completed": 0, "total": 0, "percentage": 0}),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении плана развития: {str(e)}")


@router.get("/me/library", response_model=PlanLibraryResponse)
async def get_plan_library(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    try:
        plans_res = await db.execute(
            select(DevelopmentPlan)
            .where(DevelopmentPlan.user_id == current_user.id)
            .order_by(DevelopmentPlan.generated_at.desc())
        )
        plans = plans_res.scalars().all()

        materials: list[LibraryMaterialItem] = []
        tasks: list[LibraryTaskItem] = []

        for plan in plans:
            content = plan.content
            if not isinstance(content, dict):
                continue

            plan_materials = content.get("materials")
            if isinstance(plan_materials, list):
                for m in plan_materials:
                    if not isinstance(m, dict):
                        continue
                    try:
                        materials.append(
                            LibraryMaterialItem(
                                plan_id=plan.id,
                                plan_generated_at=plan.generated_at,
                                id=str(m.get("id", "")),
                                title=str(m.get("title", "")),
                                url=str(m.get("url", "")),
                                type=str(m.get("type", "")),
                                skill=str(m.get("skill", "")),
                                difficulty=str(m.get("difficulty", "")),
                            )
                        )
                    except Exception:
                        continue

            plan_tasks = content.get("tasks")
            if isinstance(plan_tasks, list):
                for t in plan_tasks:
                    if not isinstance(t, dict):
                        continue
                    try:
                        tasks.append(
                            LibraryTaskItem(
                                plan_id=plan.id,
                                plan_generated_at=plan.generated_at,
                                id=str(t.get("id", "")),
                                description=str(t.get("description", "")),
                                skill=str(t.get("skill", "")),
                                status=str(t.get("status", "pending")),
                                completed_at=t.get("completed_at"),
                            )
                        )
                    except Exception:
                        continue

        return PlanLibraryResponse(materials=materials, tasks=tasks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении каталога: {str(e)}")


@router.post("/me/tasks/{task_id}/complete", response_model=TaskCompletionResponse)
async def complete_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    try:
        _ = background_tasks
        plan = await plan_service.get_active_plan(current_user.id, db)
        if plan is None:
            raise HTTPException(status_code=404, detail="У вас нет активного плана развития")

        updated_plan = await plan_service.mark_task_completed(
            user_id=current_user.id,
            plan_id=plan.id,
            task_id=task_id,
            db=db,
        )
        tracking = await plan_service.sync_plan_tracking(
            plan=updated_plan,
            user_id=current_user.id,
            db=db,
        )

        content = updated_plan.content if isinstance(updated_plan.content, dict) else {}
        tasks = content.get("tasks", []) if isinstance(content.get("tasks", []), list) else []
        completed_task = next((t for t in tasks if str(t.get("id")) == str(task_id)), None)
        if not completed_task:
            raise HTTPException(status_code=404, detail="Задание не найдено")

        return TaskCompletionResponse(
            task_id=task_id,
            status="completed",
            completed_at=str(completed_task.get("completed_at") or ""),
            plan_progress=float((tracking.get("progress") or {}).get("percentage") or 0),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при отметке задания: {str(e)}")


@router.post("/me/materials/{material_id}/article-open", response_model=MaterialActionResponse)
async def mark_material_article_open(
    material_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    try:
        plan = await plan_service.get_active_plan(current_user.id, db)
        if plan is None:
            raise HTTPException(status_code=404, detail="У вас нет активного плана развития")

        updated_plan = await plan_service.mark_material_article_open(
            user_id=current_user.id,
            plan_id=plan.id,
            material_id=material_id,
            db=db,
        )
        tracking = await plan_service.sync_plan_tracking(
            plan=updated_plan,
            user_id=current_user.id,
            db=db,
        )
        progress_map = tracking.get("material_progress", {})
        if not isinstance(progress_map, dict):
            progress_map = {}
        material_progress = progress_map.get(material_id, {})
        if not isinstance(material_progress, dict):
            material_progress = {}

        return MaterialActionResponse(
            material_id=material_id,
            material_percentage=float(material_progress.get("percentage") or 0),
            plan_progress=float((tracking.get("progress") or {}).get("percentage") or 0),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при отметке материала: {str(e)}")


@router.post("/me/generate", response_model=PlanGenerationResponse)
async def generate_plan_manually(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    try:
        result = await db.execute(
            select(func.count(AnalysisResult.id)).where(AnalysisResult.user_id == current_user.id)
        )
        analysis_count = result.scalar()

        min_required = settings.MIN_ANALYSES_FOR_PLAN
        if analysis_count < min_required:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Недостаточно данных для генерации плана. "
                    f"Необходимо минимум {min_required} анализа, у вас: {analysis_count}"
                ),
            )

        result = await db.execute(
            select(SoftSkillsProfile).where(SoftSkillsProfile.user_id == current_user.id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Профиль не найден. Пожалуйста, пройдите несколько тестов "
                    "или отправьте сообщения в чат."
                ),
            )

        from app.tasks.background_tasks import generate_development_plan_background

        background_tasks.add_task(
            generate_development_plan_background,
            user_id=current_user.id,
            profile_id=profile.id,
        )

        return PlanGenerationResponse(
            message="Генерация плана развития начата. Проверьте активный план через несколько секунд.",
            status="processing",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при запуске генерации плана: {str(e)}")
