from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.models.analysis import AnalysisResult as AnalysisResultModel
from app.services.analysis_service import analysis_service
from app.schemas.analysis import AnalysisStatus, AnalysisResult as AnalysisResultSchema

router = APIRouter()


@router.get("/status/{task_id}", response_model=AnalysisStatus)
async def get_analysis_status(
    task_id: str,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the status of an analysis task.
    
    Returns:
    - status: pending, processing, completed, failed
    - result: AnalysisResult if status is completed
    
    Requirements: 1.5, 6.3
    """
    try:
        status = await analysis_service.get_analysis_status(task_id, db)
        
        # Verify that the task belongs to the current user
        if status.result and status.result.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Доступ запрещен")
        
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении статуса анализа: {str(e)}")


@router.get("/me/results", response_model=list[AnalysisResultSchema])
async def get_my_analysis_results(
    limit: int = 50,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AnalysisResultModel)
        .where(AnalysisResultModel.user_id == current_user.id)
        .order_by(AnalysisResultModel.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
