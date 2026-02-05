"""
Development Plan Service for managing user development plans.
Handles plan generation, task completion tracking, and plan regeneration logic.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from sqlalchemy.orm.attributes import flag_modified

from app.models.profile import DevelopmentPlan, SoftSkillsProfile, ProfileHistory
from app.models.analysis import AnalysisResult
from app.models.content import Test
from app.schemas.plan import DevelopmentPlanContent, MaterialItem, TaskItem, TestRecommendation
from app.services.llm_service import LLMService
from app.core.config import settings

logger = logging.getLogger(__name__)


class PlanService:
    """Service for managing development plans and their lifecycle."""
    
    def __init__(self):
        self.llm_service = LLMService()

    def _curated_material_library(self) -> List[Dict[str, str]]:
        return [
            {
                "id": "ru_4brain_comm_communication",
                "title": "Эффективное общение: вербальная и невербальная коммуникация",
                "url": "https://4brain.ru/management/communication.php",
                "type": "article",
                "skill": "communication",
            },
            {
                "id": "ru_4brain_comm_nonverbal",
                "title": "Невербальная коммуникация",
                "url": "https://4brain.ru/nonverbal/",
                "type": "article",
                "skill": "communication",
            },
            {
                "id": "ru_4brain_comm_listening",
                "title": "Техники активного (глубокого) слушания",
                "url": "https://4brain.ru/blog/glubokoe-slushanie/",
                "type": "article",
                "skill": "communication",
            },
            {
                "id": "ru_4brain_comm_negotiation",
                "title": "Ведение переговоров: основы и структура",
                "url": "https://4brain.ru/peregovory/",
                "type": "article",
                "skill": "communication",
            },
            {
                "id": "ru_4brain_comm_rhetoric",
                "title": "Ораторское искусство: уроки риторики",
                "url": "https://4brain.ru/oratorskoe-iskusstvo/",
                "type": "article",
                "skill": "communication",
            },
            {
                "id": "ru_stepik_comm_effective",
                "title": "Навыки эффективной коммуникации",
                "url": "https://stepik.org/course/205042/promo",
                "type": "course",
                "skill": "communication",
            },
            {
                "id": "ru_stepik_comm_business",
                "title": "Деловые коммуникации",
                "url": "https://stepik.org/course/87737/promo",
                "type": "course",
                "skill": "communication",
            },
            {
                "id": "ru_openedu_teamwork",
                "title": "Командная работа",
                "url": "https://openedu.ru/course/ITMOUniversity/TEAMWORK/",
                "type": "course",
                "skill": "communication",
            },
            {
                "id": "ru_4brain_ei_base",
                "title": "Эмоциональный интеллект: основы и упражнения",
                "url": "https://4brain.ru/emotion/",
                "type": "article",
                "skill": "emotional_intelligence",
            },
            {
                "id": "ru_4brain_ei_article",
                "title": "Как развить эмоциональный интеллект",
                "url": "https://4brain.ru/blog/emotional-intellect/",
                "type": "article",
                "skill": "emotional_intelligence",
            },
            {
                "id": "ru_stepik_ei",
                "title": "Эмоциональный интеллект: ключ к успеху",
                "url": "https://stepik.org/course/133690/promo",
                "type": "course",
                "skill": "emotional_intelligence",
            },
            {
                "id": "ru_4brain_ct_base",
                "title": "Критическое мышление: что это и как развивать",
                "url": "https://4brain.ru/critical/",
                "type": "article",
                "skill": "critical_thinking",
            },
            {
                "id": "ru_4brain_ct_skills",
                "title": "Критическое мышление: навыки и свойства",
                "url": "https://4brain.ru/critical/navyk.php",
                "type": "article",
                "skill": "critical_thinking",
            },
            {
                "id": "ru_stepik_ct",
                "title": "Критическое мышление",
                "url": "https://stepik.org/course/63700/promo",
                "type": "course",
                "skill": "critical_thinking",
            },
            {
                "id": "ru_postnauka_ct_video",
                "title": "Критическое мышление",
                "url": "https://postnauka.ru/tv/155334",
                "type": "video",
                "skill": "critical_thinking",
            },
            {
                "id": "ru_4brain_tm_base",
                "title": "Тайм-менеджмент: управление временем",
                "url": "https://4brain.ru/time/",
                "type": "article",
                "skill": "time_management",
            },
            {
                "id": "ru_4brain_tm_basics",
                "title": "Тайм-менеджмент: основы",
                "url": "https://4brain.ru/time/osnovy.php",
                "type": "article",
                "skill": "time_management",
            },
            {
                "id": "ru_4brain_tm_psy",
                "title": "Психологические аспекты тайм-менеджмента",
                "url": "https://4brain.ru/blog/psihologiya-taym-menedzhmenta/",
                "type": "article",
                "skill": "time_management",
            },
            {
                "id": "ru_openedu_tm_course",
                "title": "Онлайн-курс: Тайм-менеджмент",
                "url": "https://openedu.ru/course/misis/TMNG/",
                "type": "course",
                "skill": "time_management",
            },
            {
                "id": "ru_stepik_tm",
                "title": "Тайм-менеджмент",
                "url": "https://stepik.org/course/102186/promo",
                "type": "course",
                "skill": "time_management",
            },
            {
                "id": "ru_4brain_lead_base",
                "title": "Лидерство: базовые принципы и подходы",
                "url": "https://4brain.ru/liderstvo/",
                "type": "article",
                "skill": "leadership",
            },
            {
                "id": "ru_4brain_lead_course",
                "title": "Лидерство и мотивация: основы",
                "url": "https://4brain.ru/management/leadership.php",
                "type": "article",
                "skill": "leadership",
            },
            {
                "id": "ru_4brain_lead_practice",
                "title": "Как быть лидером: практические советы",
                "url": "https://4brain.ru/blog/kak-byt-liderom/",
                "type": "article",
                "skill": "leadership",
            },
            {
                "id": "ru_openedu_lead_course",
                "title": "Лидерство и командообразование",
                "url": "https://openedu.ru/course/mephi/mephi_lfkpt/",
                "type": "course",
                "skill": "leadership",
            },
            {
                "id": "ru_stepik_lead_team",
                "title": "Лидерство и командообразование",
                "url": "https://stepik.org/course/83003/promo",
                "type": "course",
                "skill": "leadership",
            },
        ]

    def _material_domain(self, url: str) -> str:
        parsed = urlparse(str(url or "").strip().lower())
        return (parsed.netloc or "").lstrip("www.")

    def _weakness_to_skill(self, weakness: str) -> Optional[str]:
        w = str(weakness or "").lower()
        if "тайм" in w or "времен" in w:
            return "time_management"
        if "крит" in w:
            return "critical_thinking"
        if "коммуник" in w or "общен" in w:
            return "communication"
        if "эмоцион" in w:
            return "emotional_intelligence"
        if "лидер" in w:
            return "leadership"
        return None

    def _extract_previous_material_ids(self, plans: List[DevelopmentPlan]) -> set[str]:
        ids: set[str] = set()
        for p in plans:
            content = p.content
            if not isinstance(content, dict):
                continue
            mats = content.get("materials")
            if not isinstance(mats, list):
                continue
            for m in mats:
                if isinstance(m, dict) and m.get("id"):
                    ids.add(str(m.get("id")))
        return ids

    def _select_curated_materials(
        self,
        weaknesses: List[str],
        target_difficulty: str,
        previous_plans: List[DevelopmentPlan],
        limit: int = 7,
    ) -> List[MaterialItem]:
        library = self._curated_material_library()
        used_ids = self._extract_previous_material_ids(previous_plans)

        max_per_domain = 3

        skill_order: List[str] = []
        for w in weaknesses:
            skill = self._weakness_to_skill(w)
            if skill and skill not in skill_order:
                skill_order.append(skill)

        for skill in [
            "communication",
            "emotional_intelligence",
            "critical_thinking",
            "time_management",
            "leadership",
        ]:
            if skill not in skill_order:
                skill_order.append(skill)

        picked: List[Dict[str, str]] = []
        domain_counts: Dict[str, int] = {}

        def _can_take(candidate: Dict[str, str], ignore_domain_limit: bool = False) -> bool:
            if candidate.get("id") in used_ids:
                return False
            if candidate in picked:
                return False
            domain = self._material_domain(candidate.get("url", ""))
            if not domain:
                return False
            if ignore_domain_limit:
                return True
            return domain_counts.get(domain, 0) < max_per_domain

        def _take(candidate: Dict[str, str]) -> None:
            picked.append(candidate)
            domain = self._material_domain(candidate.get("url", ""))
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        for skill in skill_order:
            candidates = [m for m in library if m.get("skill") == skill]
            for m in candidates:
                if len(picked) >= limit:
                    break
                if not _can_take(m):
                    continue
                _take(m)
            if len(picked) >= limit:
                break

        if len(picked) < limit:
            for m in library:
                if len(picked) >= limit:
                    break
                if not _can_take(m):
                    continue
                _take(m)

        if len(picked) < limit:
            for m in library:
                if len(picked) >= limit:
                    break
                if not _can_take(m, ignore_domain_limit=True):
                    continue
                _take(m)

        picked_types = {str(m.get("type")) for m in picked}
        need_types = [t for t in ["course", "video"] if t not in picked_types]
        for t in need_types:
            replacement = next(
                (
                    m
                    for m in library
                    if str(m.get("type")) == t and _can_take(m)
                ),
                None,
            )
            if replacement is None:
                continue
            if len(picked) < limit:
                _take(replacement)
            else:
                replace_idx = next(
                    (i for i, m in enumerate(reversed(picked)) if str(m.get("type")) == "article"),
                    None,
                )
                if replace_idx is None:
                    continue
                idx = len(picked) - 1 - int(replace_idx)
                removed = picked[idx]
                removed_domain = self._material_domain(removed.get("url", ""))
                domain_counts[removed_domain] = max(0, domain_counts.get(removed_domain, 1) - 1)
                picked[idx] = replacement
                replacement_domain = self._material_domain(replacement.get("url", ""))
                domain_counts[replacement_domain] = domain_counts.get(replacement_domain, 0) + 1

        return [
            MaterialItem(
                id=str(m["id"]),
                title=str(m["title"]),
                url=str(m["url"]),
                type=str(m["type"]),
                skill=str(m["skill"]),
                difficulty=target_difficulty,
            )
            for m in picked[:limit]
        ]

    def _looks_bad_material_url(self, url: str) -> bool:
        value = str(url or "").strip().lower()
        if not value:
            return True
        if not (value.startswith("http://") or value.startswith("https://")):
            return True
        if any(token in value for token in ["example.com", "en.wikipedia.org", "ted.com", "skillbox.ru"]):
            return True
        parsed = urlparse(value)
        if not parsed.netloc:
            return True
        return False

    def _plan_materials_need_diversity_refresh(self, materials: List[Dict[str, Any]]) -> bool:
        if not materials or not isinstance(materials, list):
            return True

        domains = {
            self._material_domain(str(m.get("url")))
            for m in materials
            if isinstance(m, dict) and m.get("url")
        }
        domains.discard("")

        types = {
            str(m.get("type"))
            for m in materials
            if isinstance(m, dict) and m.get("type")
        }

        if len(domains) <= 1 and len(materials) >= 3:
            return True
        if types == {"article"} and len(materials) >= 3:
            return True
        return False

    async def sanitize_plan_materials_if_needed(
        self,
        plan: DevelopmentPlan,
        profile: SoftSkillsProfile,
        db: AsyncSession,
    ) -> bool:
        content = plan.content
        if not isinstance(content, dict):
            return False

        materials = content.get("materials")
        if not isinstance(materials, list) or not materials:
            return False

        has_bad_urls = any(
            self._looks_bad_material_url(str(m.get("url")) if isinstance(m, dict) else "")
            for m in materials
        )
        needs_diversity = self._plan_materials_need_diversity_refresh(materials)
        if not has_bad_urls and not needs_diversity:
            return False

        weaknesses = await self._identify_weaknesses(profile)
        previous_plans_result = await db.execute(
            select(DevelopmentPlan)
            .where(DevelopmentPlan.user_id == plan.user_id, DevelopmentPlan.id != plan.id)
            .order_by(desc(DevelopmentPlan.generated_at))
            .limit(3)
        )
        previous_plans = list(previous_plans_result.scalars().all())
        target_difficulty = self._resolve_target_difficulty(profile)
        curated = self._select_curated_materials(weaknesses, target_difficulty, previous_plans)
        content["materials"] = jsonable_encoder([m.dict() for m in curated])
        content["target_difficulty"] = target_difficulty
        plan.content = jsonable_encoder(content)
        flag_modified(plan, "content")
        await db.commit()
        await db.refresh(plan)
        return True

    def _resolve_target_difficulty(self, profile: SoftSkillsProfile) -> str:
        avg_score = (
            float(profile.communication_score or 0.0)
            + float(profile.emotional_intelligence_score or 0.0)
            + float(profile.critical_thinking_score or 0.0)
            + float(profile.time_management_score or 0.0)
            + float(profile.leadership_score or 0.0)
        ) / 5.0

        if avg_score >= 70:
            return "advanced"
        if avg_score >= 40:
            return "intermediate"
        return "beginner"

    def _infer_plan_difficulty(self, content: Dict[str, Any]) -> Optional[str]:
        if not isinstance(content, dict):
            return None

        value = content.get("target_difficulty")
        if isinstance(value, str) and value:
            return value

        materials = content.get("materials")
        if not isinstance(materials, list) or not materials:
            return None

        diffs = {
            str(m.get("difficulty"))
            for m in materials
            if isinstance(m, dict) and m.get("difficulty")
        }
        if len(diffs) == 1:
            return next(iter(diffs))
        return None
    
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
            generated_at = active_plan.generated_at
            now_utc = datetime.now(timezone.utc)
            if generated_at is not None and generated_at.tzinfo is None:
                generated_at = generated_at.replace(tzinfo=timezone.utc)
            days_since_generation = (now_utc - generated_at).days
            
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
        
        content = plan.content
        if not isinstance(content, dict):
            content = {}

        tasks = content.get("tasks")
        if not isinstance(tasks, list):
            tasks = []
            content["tasks"] = tasks
        
        task_found = False
        for task in tasks:
            if str(task.get("id")) == str(task_id):
                task["status"] = "completed"
                task["completed_at"] = datetime.now(timezone.utc).isoformat()
                task_found = True
                logger.info(f"Marked task {task_id} as completed in plan {plan_id}")
                break
        
        if not task_found:
            raise ValueError(f"Task {task_id} not found in plan {plan_id}")
        
        plan.content = jsonable_encoder(content)
        flag_modified(plan, "content")
        await db.commit()
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

        current_target_difficulty = self._resolve_target_difficulty(profile)
        plan_target_difficulty = self._infer_plan_difficulty(content)
        if plan_target_difficulty and plan_target_difficulty != current_target_difficulty:
            logger.info(
                "Plan %s difficulty '%s' differs from current '%s'. Triggering regeneration.",
                plan.id,
                plan_target_difficulty,
                current_target_difficulty,
            )
            return True
        
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

        target_difficulty = self._resolve_target_difficulty(profile)
        
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
                        url="https://4brain.ru/blog/glubokoe-slushanie/",
                        type="article",
                        skill="communication",
                        difficulty=target_difficulty,
                    ),
                    MaterialItem(
                        id="mat_ei_basics",
                        title="Эмоциональный интеллект: базовые принципы",
                        url="https://4brain.ru/emotion/",
                        type="article",
                        skill="emotional_intelligence",
                        difficulty=target_difficulty,
                    ),
                    MaterialItem(
                        id="mat_critical_thinking_basics",
                        title="Критическое мышление: как задавать правильные вопросы",
                        url="https://4brain.ru/critical/",
                        type="article",
                        skill="critical_thinking",
                        difficulty=target_difficulty,
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

        plan_content.materials = self._select_curated_materials(
            weaknesses=weaknesses,
            target_difficulty=target_difficulty,
            previous_plans=list(previous_plans),
        )

        plan_content.recommended_tests = await self._select_recommended_tests(weaknesses, target_difficulty, db)
        
        # Step 5: Validate material uniqueness (Requirement 4.5, Property 13)
        if previous_plans:
            most_recent_plan = previous_plans[0]
            if not self._check_material_uniqueness(plan_content, most_recent_plan):
                logger.warning(f"Generated plan for user {user_id} has less than 70% unique materials. Accepting anyway.")
        
        # Step 6: Save new plan (Requirement 3.5, Property 8)
        payload = plan_content.dict()
        payload["target_difficulty"] = target_difficulty
        new_plan = DevelopmentPlan(
            user_id=user_id,
            is_archived=False,
            content=payload
        )
        
        db.add(new_plan)
        await db.flush()
        await db.refresh(new_plan)
        
        logger.info(f"Successfully generated new development plan {new_plan.id} for user {user_id}")
        return new_plan

    async def _select_recommended_tests(self, weaknesses: List[str], target_difficulty: str, db: AsyncSession) -> List[TestRecommendation]:
        query = await db.execute(select(Test).where(Test.type != "simulation").order_by(Test.id.asc()))
        tests = list(query.scalars().all())
        if not tests:
            return []

        preferred_type = "case" if str(target_difficulty).lower() == "advanced" else "quiz"
        preferred = [t for t in tests if str(t.type).lower() == preferred_type]
        others = [t for t in tests if t not in preferred]
        tests = preferred + others

        skill_keywords = {
            "communication": ["коммуник", "communication"],
            "emotional_intelligence": ["эмоцион", "emotional", "intelligence"],
            "critical_thinking": ["крит", "critical", "мышлен"],
            "time_management": ["тайм", "time", "management"],
            "leadership": ["лидер", "leadership", "lead"],
        }

        def _resolve_keywords(weakness: str) -> List[str]:
            if not weakness:
                return []
            normalized = weakness.lower().replace("-", " ").replace("_", " ")
            for keywords in skill_keywords.values():
                if any(keyword in normalized for keyword in keywords):
                    return keywords
            return []

        picked: List[Test] = []
        for w in weaknesses:
            keywords = _resolve_keywords(w)
            for t in tests:
                hay = f"{t.title} {t.description}".lower()
                if any(k in hay for k in keywords):
                    if t not in picked:
                        picked.append(t)
                    break

        for t in tests:
            if len(picked) >= 3:
                break
            if t not in picked:
                picked.append(t)

        reason = "Рекомендуем пройти тесты, чтобы собрать больше данных и улучшить слабые навыки." if weaknesses else "Рекомендуем пройти тесты для накопления данных." 
        return [
            TestRecommendation(test_id=int(t.id), title=t.title, reason=reason)
            for t in picked[:3]
        ]
    
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
            ("Тайм-менеджмент", profile.time_management_score),
            ("Критическое мышление", profile.critical_thinking_score),
            ("Коммуникация", profile.communication_score),
            ("Эмоциональный интеллект", profile.emotional_intelligence_score),
            ("Лидерство", profile.leadership_score)
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
