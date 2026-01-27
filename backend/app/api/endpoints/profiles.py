from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api import deps
from app.db.session import get_db
from app.models.profile import SoftSkillsProfile
from app.models.user import User
from app.schemas.content import SoftSkillsProfile as ProfileSchema
from app.schemas.profile import ProfileWithHistory
from app.services.profile_service import profile_service

router = APIRouter()

@router.get("/me", response_model=ProfileSchema)
async def read_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current user's soft skills profile.
    """
    result = await db.execute(select(SoftSkillsProfile).where(SoftSkillsProfile.user_id == current_user.id))
    profile = result.scalars().first()
    
    if not profile:
        # Create empty profile if not exists
        profile = SoftSkillsProfile(user_id=current_user.id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        
    return profile


@router.get("/me/history", response_model=ProfileWithHistory)
async def read_my_profile_history(
    months: int = Query(default=6, ge=1, le=24, description="Number of months of history to retrieve"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current user's soft skills profile with historical data.
    
    Returns:
    - current: Current skill scores
    - history: Historical snapshots for the specified time period
    - strengths: Top-3 skills with highest scores
    - weaknesses: Top-3 skills with lowest scores
    
    Requirements: 2.3, 2.4, 2.5, 7.4
    """
    profile_with_history = await profile_service.get_profile_with_history(
        user_id=current_user.id,
        months=months,
        db=db
    )
    
    return profile_with_history

