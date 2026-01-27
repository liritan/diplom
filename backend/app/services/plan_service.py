"""
Development Plan Service for managing user development plans.
Handles plan generation, task completion tracking, and plan regeneration logic.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func

from app.models.profile import DevelopmentPlan, SoftSkillsProfile, ProfileHistory
from app.models.analysis import AnalysisResult
from app.schemas.plan import DevelopmentPlanContent, MaterialItem, TaskItem, TestRecommendation
from app.services.llm_service import LLMService
from app.core.config import settings

logger = logging.getLogger(__name__)


class PlanService:
    """Service for managing development plans and their lifecycle."""
    
    def __init__(self):
        self.llm_service = LLMService()
    
    async def check_and_generate_plan(
        self,
        user_id: int,
        profile: SoftSkillsProfile,
        db: AsyncSession
    ) -> Optional[DevelopmentPlan]:
        """
        Check if a new development plan should be generated and generate it if needed.
        
        Conditions for generation:
        - More than 7 days since last plan generation
        - No active plan exists
        - User has at least 3 completed analyses
        
        Args:
            user_id: User ID
            profile: User's current soft skills profile
            db: Database session
            
        Returns:
            Optional[DevelopmentPlan]: Newly generated plan or None if conditions not met
            
        Requirements: 3.1, 6.5
        Property 6: Development Plan Generation Trigger
        """
        # Check if user has enough completed analyses (Requirement 6.5)
        analysis_count_result = await db.execute(
            select(func.count(AnalysisResult.id))
            .where(AnalysisResult.user_id == user_id)
        )
        analysis_count = analysis_count_result.scalar()

        min_required = settings.MIN_ANALYSES_FOR_PLAN
        if analysis_count < min_required:
            logger.info(
                f"User {user_id} has only {analysis_count} analyses. Need at least {min_required} for plan generation."
            )
            return None
        
        # Check for existing active plan
        active_plan = await self.get_active_plan(user_id, db)
        
        # Check if we need to generate a new plan
        should_generate = False
        
        if active_plan is None:
            # No active plan exists
            logger.info(f"No active plan exists for user {user_id}. Will generate new plan.")
            should_generate = True
        else:
            # Check if more than 7 days have passed since last generation (Requirement 3.1)
            days_since_generation = (datetime.utcnow() - active_plan.generated_at).days
            
            if days_since_generation > 7:
                logger.info(f"Last plan for user {user_id} was generated {days_since_generation} days ago. Will generate new plan.")
                should_generate = True
            else:
                # Check if plan should be regenerated based on progress
                if await self._should_regenerate_plan(active_plan, profile, db):
                    logger.info(f"Plan regeneration triggered for user {user_id} based on progress.")
                    should_generate = True
        
        if not should_generate:
            logger.info(f"No plan generation needed for user {user_id}.")
            return None
        
        # Generate new plan
        return await self._generate_new_plan(user_id, profile, db)
    
    async def mark_task_completed(
        self,
        user_id: int,
        plan_id: int,
        task_id: str,
        db: AsyncSession
    ) -> DevelopmentPlan:
        """
        Mark a task in the development plan as completed.
        
        Args:
            user_id: User ID
            plan_id: Development plan ID
            task_id: Task ID within the plan
            db: Database session
            
        Returns:
            DevelopmentPlan: Updated development plan
            
        Raises:
            ValueError: If plan or task not found
            
        Requirements: 4.1
        Property 9: Task Completion Tracking
        """
        # Get the plan
        result = await db.execute(
            select(DevelopmentPlan)
            .where(
                and_(
                    DevelopmentPlan.id == plan_id,
                    DevelopmentPlan.user_id == user_id,
                    DevelopmentPlan.is_archived == False
                )
            )
        )
        plan = result.scalar_one_or_none()
        
        if plan is None:
            raise ValueError(f"Active plan {plan_id} not found for user {user_id}")
        
        # Update task status in content JSON
        content = plan.content
        if not content or "tasks" not in content:
            raise ValueError(f"Plan {plan_id} has invalid content structure")
        
        task_found = False
        for task in content["tasks"]:
            if task.get("id") == task_id:
                task["status"] = "completed"
                task["completed_at"] = datetime.utcnow().isoformat()
                task_found = True
                logger.info(f"Marked task {task_id} as completed in plan {plan_id}")
                break
        
        if not task_found:
            raise ValueError(f"Task {task_id} not found in plan {plan_id}")
        
        # Update the plan
        plan.content = content
        await db.flush()
        await db.refresh(plan)
        
        return plan
    
    async def get_active_plan(
        self,
        user_id: int,
        db: AsyncSession
    ) -> Optional[DevelopmentPlan]:
        """
        Get the active (non-archived) development plan for a user.
        
        Args:
            user_id: User ID
            db: Database session
            
        Returns:
            Optional[DevelopmentPlan]: Active plan or None if no active plan exists
            
        Requirements: 4.4
        Property 12: Plan Response Completeness
        """
        result = await db.execute(
            select(DevelopmentPlan)
            .where(
                and_(
                    DevelopmentPlan.user_id == user_id,
                    DevelopmentPlan.is_archived == False
                )
            )
            .order_by(desc(DevelopmentPlan.generated_at))
        )
        plan = result.scalar_one_or_none()
        
        return plan
    
    async def _should_regenerate_plan(
        self,
        plan: DevelopmentPlan,
        profile: SoftSkillsProfile,
        db: AsyncSession
    ) -> bool:
        """
        Determine if a plan should be regenerated based on user progress.
        
        Conditions for regeneration:
        - 70% or more of tasks are completed
        - Any skill has improved by 15+ points since plan generation
        
        Args:
            plan: Current development plan
            profile: Current user profile
            db: Database session
            
        Returns:
            bool: True if plan should be regenerated
            
        Requirements: 4.2, 4.3
        Property 10: Plan Regeneration on Progress
        Property 11: Skill Improvement Detection
        """
        # Check task completion percentage (Requirement 4.2)
        content = plan.content
        if not content or "tasks" not in content:
            return False
        
        tasks = content["tasks"]
        if not tasks:
            return False
        
        completed_tasks = sum(1 for task in tasks if task.get("status") == "completed")
        total_tasks = len(tasks)
        completion_percentage = (completed_tasks / total_tasks) * 100
        
        if completion_percentage >= 70:
            logger.info(f"Plan {plan.id} has {completion_percentage:.1f}% tasks completed. Triggering regeneration.")
            return True
        
        # Check skill improvement (Requirement 4.3)
        # Get profile state at the time of plan generation
        result = await db.execute(
            select(ProfileHistory)
            .where(
                and_(
                    ProfileHistory.user_id == plan.user_id,
                    ProfileHistory.created_at <= plan.generated_at
                )
            )
            .order_by(desc(ProfileHistory.created_at))
            .limit(1)
        )
        historical_profile = result.scalar_one_or_none()
        
        if historical_profile:
            # Compare current scores with historical scores
            skills = [
                ("communication", profile.communication_score, historical_profile.communication_score),
                ("emotional_intelligence", profile.emotional_intelligence_score, historical_profile.emotional_intelligence_score),
                ("critical_thinking", profile.critical_thinking_score, historical_profile.critical_thinking_score),
                ("time_management", profile.time_management_score, historical_profile.time_management_score),
                ("leadership", profile.leadership_score, historical_profile.leadership_score)
            ]
            
            for skill_name, current_score, historical_score in skills:
                improvement = current_score - historical_score
                if improvement >= 15:
                    logger.info(f"Skill {skill_name} improved by {improvement:.1f} points. Triggering plan regeneration.")
                    return True
        
        return False
    
    async def _generate_new_plan(
        self,
        user_id: int,
        profile: SoftSkillsProfile,
        db: AsyncSession
    ) -> DevelopmentPlan:
        """
        Generate a new development plan for the user.
        
        Steps:
        1. Archive existing active plan
        2. Identify weaknesses from profile
        3. Get previous plans to avoid material repetition
        4. Generate plan using LLM
        5. Validate material uniqueness
        6. Save new plan
        
        Args:
            user_id: User ID
            profile: User's current profile
            db: Database session
            
        Returns:
            DevelopmentPlan: Newly created development plan
            
        Requirements: 3.2, 3.3, 3.4, 3.5, 7.3, 4.5
        Property 7: Development Plan Content Structure
        Property 8: Development Plan Persistence
        Property 13: Material Uniqueness Across Plans
        Property 24: Plan Archival on Regeneration
        """
        # Step 1: Archive existing active plan (Requirement 7.3, Property 24)
        await self._archive_active_plan(user_id, db)
        
        # Step 2: Identify weaknesses
        weaknesses = await self._identify_weaknesses(profile)
        
        # Step 3: Get previous plans for material uniqueness check
        previous_plans_result = await db.execute(
            select(DevelopmentPlan)
            .where(DevelopmentPlan.user_id == user_id)
            .order_by(desc(DevelopmentPlan.generated_at))
            .limit(3)  # Consider last 3 plans
        )
        previous_plans = previous_plans_result.scalars().all()
        
        # Step 4: Generate plan using LLM (Requirements 3.2, 3.3, 3.4)
        try:
            plan_content = await self.llm_service.generate_development_plan(
                profile=profile,
                weaknesses=weaknesses,
                history=list(previous_plans)
            )
        except Exception as e:
            logger.error(f"Failed to generate plan via LLM for user {user_id}: {e}")
            plan_content = DevelopmentPlanContent(
                weaknesses=weaknesses,
                materials=[
                    MaterialItem(
                        id="mat_communication_basics",
                        title="Основы коммуникации: активное слушание",
                        url="https://en.wikipedia.org/wiki/Active_listening",
                        type="article",
                        skill="communication",
                        difficulty="beginner",
                    ),
                    MaterialItem(
                        id="mat_ei_basics",
                        title="Эмоциональный интеллект: базовые принципы",
                        url="https://en.wikipedia.org/wiki/Emotional_intelligence",
                        type="article",
                        skill="emotional_intelligence",
                        difficulty="beginner",
                    ),
                    MaterialItem(
                        id="mat_critical_thinking_basics",
                        title="Критическое мышление: как задавать правильные вопросы",
                        url="https://en.wikipedia.org/wiki/Critical_thinking",
                        type="article",
                        skill="critical_thinking",
                        difficulty="beginner",
                    ),
                ],
                tasks=[
                    TaskItem(
                        id="task_reflect_1",
                        description="После диалога запишите 3 пункта: что получилось, что можно улучшить, какой следующий шаг.",
                        skill="communication",
                        status="pending",
                        completed_at=None,
                    ),
                    TaskItem(
                        id="task_ei_1",
                        description="В следующей сложной ситуации попробуйте назвать эмоции собеседника и уточнить их вопросом.",
                        skill="emotional_intelligence",
                        status="pending",
                        completed_at=None,
                    ),
                    TaskItem(
                        id="task_ct_1",
                        description="Перед решением задачи сформулируйте 5 уточняющих вопросов (что неизвестно, какие ограничения).",
                        skill="critical_thinking",
                        status="pending",
                        completed_at=None,
                    ),
                ],
                recommended_tests=[
                    TestRecommendation(
                        test_id=0,
                        title="Любой доступный тест",
                        reason="Пока сервис генерации рекомендаций недоступен — пройдите тесты из раздела 'Тесты' для накопления данных.",
                    )
                ],
            )
        
        # Step 5: Validate material uniqueness (Requirement 4.5, Property 13)
        if previous_plans:
            most_recent_plan = previous_plans[0]
            if not self._check_material_uniqueness(plan_content, most_recent_plan):
                logger.warning(f"Generated plan for user {user_id} has less than 70% unique materials. Accepting anyway.")
        
        # Step 6: Save new plan (Requirement 3.5, Property 8)
        new_plan = DevelopmentPlan(
            user_id=user_id,
            is_archived=False,
            content=plan_content.dict()
        )
        
        db.add(new_plan)
        await db.flush()
        await db.refresh(new_plan)
        
        logger.info(f"Successfully generated new development plan {new_plan.id} for user {user_id}")
        return new_plan
    
    async def _archive_active_plan(
        self,
        user_id: int,
        db: AsyncSession
    ) -> None:
        """
        Archive the current active plan before creating a new one.
        
        Args:
            user_id: User ID
            db: Database session
            
        Requirements: 7.3
        Property 24: Plan Archival on Regeneration
        """
        result = await db.execute(
            select(DevelopmentPlan)
            .where(
                and_(
                    DevelopmentPlan.user_id == user_id,
                    DevelopmentPlan.is_archived == False
                )
            )
        )
        active_plan = result.scalar_one_or_none()
        
        if active_plan:
            active_plan.is_archived = True
            await db.flush()
            logger.info(f"Archived plan {active_plan.id} for user {user_id}")
    
    async def _identify_weaknesses(
        self,
        profile: SoftSkillsProfile
    ) -> List[str]:
        """
        Identify the weakest skills from the profile.
        
        Args:
            profile: User's soft skills profile
            
        Returns:
            List[str]: List of weakness names (bottom 3 skills)
            
        Requirements: 2.5
        """
        skills = [
            ("Time Management", profile.time_management_score),
            ("Critical Thinking", profile.critical_thinking_score),
            ("Communication", profile.communication_score),
            ("Emotional Intelligence", profile.emotional_intelligence_score),
            ("Leadership", profile.leadership_score)
        ]
        
        # Sort by score (ascending) to get weaknesses
        sorted_skills = sorted(skills, key=lambda x: x[1])
        
        # Return bottom 3 as weaknesses
        weaknesses = [skill[0] for skill in sorted_skills[:3]]
        
        return weaknesses
    
    def _check_material_uniqueness(
        self,
        new_plan_content: DevelopmentPlanContent,
        previous_plan: DevelopmentPlan
    ) -> bool:
        """
        Check if new plan has at least 70% unique materials compared to previous plan.
        
        Args:
            new_plan_content: Content of the new plan
            previous_plan: Previous development plan
            
        Returns:
            bool: True if at least 70% of materials are unique
            
        Requirements: 4.5
        Property 13: Material Uniqueness Across Plans
        """
        if not previous_plan.content or "materials" not in previous_plan.content:
            return True
        
        # Extract material IDs from both plans
        new_material_ids = {material.id for material in new_plan_content.materials}
        previous_material_ids = {
            material.get("id") 
            for material in previous_plan.content["materials"]
            if material.get("id")
        }
        
        if not new_material_ids:
            return True
        
        # Calculate uniqueness
        common_materials = new_material_ids.intersection(previous_material_ids)
        unique_materials = new_material_ids - previous_material_ids
        
        uniqueness_percentage = (len(unique_materials) / len(new_material_ids)) * 100
        
        logger.info(f"Material uniqueness: {uniqueness_percentage:.1f}% ({len(unique_materials)}/{len(new_material_ids)} unique)")
        
        return uniqueness_percentage >= 70


# Create a singleton instance
plan_service = PlanService()
