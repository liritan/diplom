from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.models.profile import SoftSkillsProfile
from app.models.analysis import AnalysisResult
from app.schemas.plan import DevelopmentPlanWithProgress
from app.services.plan_service import plan_service
from app.core.config import settings

router = APIRouter()


class TaskCompletionResponse(BaseModel):
    """Response for task completion"""
    task_id: str
    status: str
    completed_at: str
    plan_progress: float


class PlanGenerationResponse(BaseModel):
    """Response for manual plan generation"""
    message: str
    status: str


@router.get("/me/active", response_model=Optional[DevelopmentPlanWithProgress])
async def get_active_plan(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get the current user's active development plan with progress tracking.
    
    Returns:
    - Active development plan with all materials, tasks, and recommendations
    - Progress tracking: completed tasks, total tasks, completion percentage
    - Returns None if no active plan exists
    
    Requirements: 4.4
    """
    try:
        plan = await plan_service.get_active_plan(current_user.id, db)
        
        if plan is None:
            return None
        
        # Parse content JSON
        content = plan.content
        tasks = content.get("tasks", [])
        
        # Calculate progress
        completed_tasks = sum(1 for task in tasks if task.get("status") == "completed")
        total_tasks = len(tasks)
        percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Build response
        return DevelopmentPlanWithProgress(
            id=plan.id,
            user_id=plan.user_id,
            generated_at=plan.generated_at,
            is_archived=plan.is_archived,
            weaknesses=content.get("weaknesses", []),
            materials=content.get("materials", []),
            tasks=tasks,
            recommended_tests=content.get("recommended_tests", []),
            progress={
                "completed": completed_tasks,
                "total": total_tasks,
                "percentage": round(percentage, 2)
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении плана развития: {str(e)}")


@router.post("/me/tasks/{task_id}/complete", response_model=TaskCompletionResponse)
async def complete_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Mark a task in the development plan as completed.
    
    Updates:
    - Task status to "completed"
    - Task completed_at timestamp
    - Checks if plan regeneration is needed (70%+ tasks completed or skill improvement)
    
    Requirements: 4.1, 4.2
    """
    try:
        # Get active plan
        plan = await plan_service.get_active_plan(current_user.id, db)
        
        if plan is None:
            raise HTTPException(status_code=404, detail="У вас нет активного плана развития")
        
        # Mark task as completed
        updated_plan = await plan_service.mark_task_completed(
            user_id=current_user.id,
            plan_id=plan.id,
            task_id=task_id,
            db=db
        )
        
        # Calculate progress
        content = updated_plan.content
        tasks = content.get("tasks", [])
        completed_tasks = sum(1 for task in tasks if task.get("status") == "completed")
        total_tasks = len(tasks)
        percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Find the completed task to get its completed_at timestamp
        completed_task = next((t for t in tasks if t.get("id") == task_id), None)
        if not completed_task:
            raise HTTPException(status_code=404, detail="Задание не найдено")
        
        # Check if plan regeneration is needed (handled in background)
        # This is checked in mark_task_completed method
        
        return TaskCompletionResponse(
            task_id=task_id,
            status="completed",
            completed_at=completed_task.get("completed_at", ""),
            plan_progress=round(percentage, 2)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при отметке задания: {str(e)}")


@router.post("/me/generate", response_model=PlanGenerationResponse)
async def generate_plan_manually(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Manually trigger development plan generation.
    
    Checks:
    - User must have at least 3 completed analyses
    - Triggers background task for plan generation
    
    Requirements: 3.1, 6.5
    """
    try:
        # Check if user has enough analyses (Requirement 6.5)
        result = await db.execute(
            select(func.count(AnalysisResult.id))
            .where(AnalysisResult.user_id == current_user.id)
        )
        analysis_count = result.scalar()

        min_required = settings.MIN_ANALYSES_FOR_PLAN
        if analysis_count < min_required:
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно данных для генерации плана. Необходимо минимум {min_required} анализа, у вас: {analysis_count}"
            )
        
        # Get user's profile
        result = await db.execute(
            select(SoftSkillsProfile).where(SoftSkillsProfile.user_id == current_user.id)
        )
        profile = result.scalar_one_or_none()
        
        if not profile:
            raise HTTPException(
                status_code=404,
                detail="Профиль не найден. Пожалуйста, пройдите несколько тестов или отправьте сообщения в чат."
            )
        
        # Trigger plan generation in background
        from app.tasks.background_tasks import generate_development_plan_background
        background_tasks.add_task(
            generate_development_plan_background,
            user_id=current_user.id,
            profile_id=profile.id
        )
        
        return PlanGenerationResponse(
            message="Генерация плана развития начата. Проверьте активный план через несколько секунд.",
            status="processing"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при запуске генерации плана: {str(e)}")


