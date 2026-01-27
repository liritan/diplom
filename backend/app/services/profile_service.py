from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.models.profile import SoftSkillsProfile, ProfileHistory
from app.schemas.analysis import SkillScores
from app.schemas.profile import ProfileWithHistory, StrengthsWeaknesses


class ProfileService:
    """Service for managing Soft Skills profiles and their history"""
    
    def __init__(self):
        pass
    
    async def update_profile(
        self,
        user_id: int,
        new_scores: SkillScores,
        weight: float,
        db: AsyncSession
    ) -> SoftSkillsProfile:
        """
        Update user's soft skills profile using weighted average.
        
        Args:
            user_id: User ID
            new_scores: New skill scores from analysis
            weight: Weight for new scores (0-1), where 1 means 100% new scores
            db: Database session
            
        Returns:
            Updated SoftSkillsProfile
            
        Requirements: 2.1, 2.2, 7.2
        """
        # Get or create profile
        result = await db.execute(
            select(SoftSkillsProfile).where(SoftSkillsProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        
        if profile is None:
            # Create new profile with initial scores
            profile = SoftSkillsProfile(
                user_id=user_id,
                communication_score=new_scores.communication,
                emotional_intelligence_score=new_scores.emotional_intelligence,
                critical_thinking_score=new_scores.critical_thinking,
                time_management_score=new_scores.time_management,
                leadership_score=new_scores.leadership
            )
            db.add(profile)
            await db.flush()
            await db.refresh(profile)
            return profile
        
        # Save current state to history before updating (Requirement 2.2, 7.2)
        await self._save_profile_history(profile, db)
        
        # Update scores using weighted average
        profile.communication_score = self._calculate_weighted_average(
            profile.communication_score, new_scores.communication, weight
        )
        profile.emotional_intelligence_score = self._calculate_weighted_average(
            profile.emotional_intelligence_score, new_scores.emotional_intelligence, weight
        )
        profile.critical_thinking_score = self._calculate_weighted_average(
            profile.critical_thinking_score, new_scores.critical_thinking, weight
        )
        profile.time_management_score = self._calculate_weighted_average(
            profile.time_management_score, new_scores.time_management, weight
        )
        profile.leadership_score = self._calculate_weighted_average(
            profile.leadership_score, new_scores.leadership, weight
        )
        
        await db.flush()
        await db.refresh(profile)
        return profile
    
    async def get_profile_with_history(
        self,
        user_id: int,
        months: int,
        db: AsyncSession
    ) -> Optional[ProfileWithHistory]:
        """
        Get user's profile with historical data.
        
        Args:
            user_id: User ID
            months: Number of months of history to retrieve
            db: Database session
            
        Returns:
            ProfileWithHistory or None if profile doesn't exist
            
        Requirements: 2.3, 2.4, 2.5, 7.4
        """
        # Get current profile
        result = await db.execute(
            select(SoftSkillsProfile).where(SoftSkillsProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        
        if profile is None:
            return None
        
        # Get history for specified time range (Requirement 7.4)
        cutoff_date = datetime.utcnow() - timedelta(days=months * 30)
        history_result = await db.execute(
            select(ProfileHistory)
            .where(
                and_(
                    ProfileHistory.user_id == user_id,
                    ProfileHistory.created_at >= cutoff_date
                )
            )
            .order_by(ProfileHistory.created_at.desc())
        )
        history_records = history_result.scalars().all()
        
        # Build current scores dict
        current_scores = {
            "communication": profile.communication_score,
            "emotional_intelligence": profile.emotional_intelligence_score,
            "critical_thinking": profile.critical_thinking_score,
            "time_management": profile.time_management_score,
            "leadership": profile.leadership_score
        }
        
        # Identify strengths and weaknesses (Requirements 2.4, 2.5)
        strengths_weaknesses = await self.identify_strengths_weaknesses(profile)
        
        return ProfileWithHistory(
            current=current_scores,
            history=[
                {
                    "id": h.id,
                    "user_id": h.user_id,
                    "profile_id": h.profile_id,
                    "communication_score": h.communication_score,
                    "emotional_intelligence_score": h.emotional_intelligence_score,
                    "critical_thinking_score": h.critical_thinking_score,
                    "time_management_score": h.time_management_score,
                    "leadership_score": h.leadership_score,
                    "created_at": h.created_at
                }
                for h in history_records
            ],
            strengths=strengths_weaknesses.strengths,
            weaknesses=strengths_weaknesses.weaknesses
        )
    
    async def identify_strengths_weaknesses(
        self,
        profile: SoftSkillsProfile
    ) -> StrengthsWeaknesses:
        """
        Identify top-3 strengths and weaknesses from profile.
        
        Args:
            profile: SoftSkillsProfile instance
            
        Returns:
            StrengthsWeaknesses with top-3 strengths and weaknesses
            
        Requirements: 2.4, 2.5
        """
        # Create list of (skill_name, score) tuples
        skills = [
            ("Communication", profile.communication_score),
            ("Emotional Intelligence", profile.emotional_intelligence_score),
            ("Critical Thinking", profile.critical_thinking_score),
            ("Time Management", profile.time_management_score),
            ("Leadership", profile.leadership_score)
        ]
        
        # Sort by score
        sorted_skills = sorted(skills, key=lambda x: x[1], reverse=True)
        
        # Top-3 are strengths, bottom-3 are weaknesses
        strengths = [skill[0] for skill in sorted_skills[:3]]
        weaknesses = [skill[0] for skill in sorted_skills[-3:]]
        weaknesses.reverse()  # Show weakest first
        
        return StrengthsWeaknesses(
            strengths=strengths,
            weaknesses=weaknesses
        )
    
    def _calculate_weighted_average(
        self,
        old_score: float,
        new_score: float,
        weight: float
    ) -> float:
        """
        Calculate weighted average of old and new scores.
        
        Args:
            old_score: Previous score (0-100)
            new_score: New score (0-100)
            weight: Weight for new score (0-1)
            
        Returns:
            Weighted average, clamped to [0, 100]
            
        Requirements: 2.1
        Property 3: For any old_score and new_score in [0, 100] and weight in [0, 1],
                   result must be in [0, 100]
        """
        # Calculate weighted average: old_score * (1 - weight) + new_score * weight
        result = old_score * (1 - weight) + new_score * weight
        
        # Clamp to [0, 100] to guarantee bounds (Property 3)
        return max(0.0, min(100.0, result))
    
    async def _save_profile_history(
        self,
        profile: SoftSkillsProfile,
        db: AsyncSession
    ) -> None:
        """
        Save current profile state to history before updating.
        
        Args:
            profile: Current profile to snapshot
            db: Database session
            
        Requirements: 2.2, 7.2
        Property 23: Profile history snapshot must be created before each update
        """
        history_entry = ProfileHistory(
            user_id=profile.user_id,
            profile_id=profile.id,
            communication_score=profile.communication_score,
            emotional_intelligence_score=profile.emotional_intelligence_score,
            critical_thinking_score=profile.critical_thinking_score,
            time_management_score=profile.time_management_score,
            leadership_score=profile.leadership_score
        )
        db.add(history_entry)
        await db.flush()


profile_service = ProfileService()
