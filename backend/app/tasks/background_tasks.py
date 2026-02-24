"""
Background tasks for processing analysis and generating development plans.

This module contains background task functions that are executed asynchronously
using FastAPI BackgroundTasks for serverless deployment compatibility.
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.analysis import AnalysisTask, AnalysisResult
from app.models.chat import ChatMessage, ChatAudio
from app.models.content import UserTestResult, CaseSolution, Test
from app.models.profile import SoftSkillsProfile
from app.services.llm_service import LLMService, LLMUnavailableError, LLMRateLimitError, LLMInvalidResponseError
from app.services.profile_service import ProfileService
from app.services.plan_service import PlanService
from app.schemas.analysis import SkillScores

logger = logging.getLogger(__name__)


async def process_analysis_background(
    task_id: str,
    user_id: int,
    response_type: str,
    response_data: Dict[str, Any]
) -> None:
    """
    Background task to process analysis of user response.
    
    Steps:
    1. Get response data from database
    2. Call LLMService for analysis
    3. Save AnalysisResult
    4. Update SoftSkillsProfile through ProfileService
    5. Check if development plan generation is needed
    6. Handle errors with logging
    
    Args:
        task_id: Analysis task ID
        user_id: User ID
        response_type: Type of response ('chat', 'test', 'case')
        response_data: Data containing the response to analyze
        
    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 3.1
    """
    logger.info(
        f"Background analysis task started: task_id={task_id}, "
        f"user_id={user_id}, type={response_type}"
    )
    
    # Create a new database session for this background task
    async with AsyncSessionLocal() as db:
        try:
            # Use timeout for serverless compatibility (Requirement 6.1, 6.3)
            await asyncio.wait_for(
                _process_analysis_with_db(task_id, user_id, response_type, response_data, db),
                timeout=120.0
            )
            
        except asyncio.TimeoutError:
            logger.error(f"Analysis task {task_id} timed out after 120 seconds")
            # Update task status to failed
            await _mark_task_failed(task_id, "Analysis timed out after 120 seconds", db)
            
        except Exception as e:
            logger.error(f"Error processing analysis task {task_id}: {str(e)}", exc_info=True)
            # Update task status to failed
            await _mark_task_failed(task_id, str(e), db)


async def _process_analysis_with_db(
    task_id: str,
    user_id: int,
    response_type: str,
    response_data: Dict[str, Any],
    db: AsyncSession
) -> None:
    """
    Internal function to process analysis with database session.
    
    Requirements: 1.5, 2.1, 3.1
    """
    # Update task status to processing
    result = await db.execute(
        select(AnalysisTask).where(AnalysisTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        logger.error(f"Analysis task {task_id} not found")
        return
    
    task.status = "processing"
    await db.commit()
    
    # Step 1: Get response data from database (if needed)
    text_to_analyze = None
    context = None
    
    if response_type == "chat":
        # Get chat message
        message_id = response_data.get("response_id")
        if message_id:
            msg_result = await db.execute(
                select(ChatMessage).where(ChatMessage.id == message_id)
            )
            chat_message = msg_result.scalar_one_or_none()
            if chat_message:
                text_to_analyze = chat_message.message
                audio_row = await db.execute(
                    select(ChatAudio).where(ChatAudio.chat_message_id == chat_message.id)
                )
                has_audio = audio_row.scalar_one_or_none() is not None
                context = (
                    "Анализ голосового сообщения пользователя (текст распознан из аудио; учитывай сарказм/иронию)"
                    if has_audio
                    else "Анализ текстового сообщения пользователя"
                )
        else:
            text_to_analyze = response_data.get("message")
            context = "Анализ текстового сообщения пользователя"
    
    elif response_type == "test":
        test_id = response_data.get("test_id")
        result_id = response_data.get("result_id")

        answers = response_data.get("answers", {})
        if result_id:
            result_row = await db.execute(
                select(UserTestResult).where(UserTestResult.id == int(result_id))
            )
            test_result = result_row.scalar_one_or_none()
            if test_result:
                answers = test_result.details or {}

        response_data["answers"] = answers

        context = f"Анализ результатов теста ID {test_id}"

    elif response_type == "case":
        solution_id = response_data.get("solution_id")
        case_id = response_data.get("case_id")
        if solution_id:
            solution_row = await db.execute(
                select(CaseSolution).where(CaseSolution.id == int(solution_id))
            )
            case_solution = solution_row.scalar_one_or_none()
            if case_solution:
                text_to_analyze = case_solution.solution
        else:
            text_to_analyze = response_data.get("solution")

        context = f"Анализ решения кейса ID {case_id}"
    
    # Step 2: Call LLMService for analysis (Requirement 1.5)
    llm_service = LLMService()
    skill_scores = None
    
    try:
        if response_type == "test":
            test_id = response_data.get("test_id")
            result_id = response_data.get("result_id")
            answers = response_data.get("answers", {})

            questions = []
            if test_id:
                test_row = await db.execute(
                    select(Test).options(selectinload(Test.questions)).where(Test.id == int(test_id))
                )
                test_obj = test_row.scalar_one_or_none()
                if test_obj and test_obj.questions:
                    questions = [
                        {"id": q.id, "text": q.text}
                        for q in test_obj.questions
                    ]

            if not questions:
                questions = [
                    {"id": k, "text": f"Question {k}"}
                    for k in answers.keys()
                ]

            skill_scores = await llm_service.analyze_test_answers(
                test_type=f"test_{test_id}",
                questions=questions,
                answers=answers
            )
        else:
            # For chat and case, analyze the text
            if not text_to_analyze:
                raise ValueError(f"No text to analyze for {response_type}")
            
            skill_scores = await llm_service.analyze_communication(
                text=text_to_analyze,
                context=context
            )
        
        logger.info(f"LLM analysis completed for task {task_id}: {skill_scores}")
        
    except LLMUnavailableError as e:
        # LLM is unavailable - save for retry (Requirement 6.1)
        logger.error(f"LLM unavailable for task {task_id}: {str(e)}")
        # Mark task as failed with clear message for retry
        task.status = "failed"
        task.error_message = f"LLM unavailable: {str(e)}"
        task.retry_count += 1
        await db.commit()
        logger.info(f"Task {task_id} marked for retry (attempt {task.retry_count}/3)")
        return
        
    except LLMRateLimitError as e:
        # Rate limit exceeded - save for retry (Requirement 6.1)
        logger.error(f"Rate limit exceeded for task {task_id}: {str(e)}")
        task.status = "failed"
        task.error_message = f"Rate limit exceeded: {str(e)}"
        task.retry_count += 1
        await db.commit()
        logger.info(f"Task {task_id} marked for retry due to rate limit (attempt {task.retry_count}/3)")
        return
        
    except LLMInvalidResponseError as e:
        # Invalid response after retries - save for retry (Requirement 6.1)
        logger.error(f"Invalid LLM response for task {task_id}: {str(e)}")
        task.status = "failed"
        task.error_message = f"Invalid response: {str(e)}"
        task.retry_count += 1
        await db.commit()
        logger.info(f"Task {task_id} marked for retry due to invalid response (attempt {task.retry_count}/3)")
        return
        
    except Exception as e:
        logger.error(f"LLM analysis failed for task {task_id}: {str(e)}")
        raise
    
    # Step 3: Save AnalysisResult (Requirement 1.5)
    analysis_result = AnalysisResult(
        task_id=task_id,
        user_id=user_id,
        communication_score=skill_scores.communication,
        emotional_intelligence_score=skill_scores.emotional_intelligence,
        critical_thinking_score=skill_scores.critical_thinking,
        time_management_score=skill_scores.time_management,
        leadership_score=skill_scores.leadership,
        strengths=[],
        weaknesses=[],
        feedback=skill_scores.feedback or ""
    )
    db.add(analysis_result)
    await db.flush()
    
    # Step 4: Update SoftSkillsProfile through ProfileService (Requirement 2.1)
    profile_service = ProfileService()
    weight = 0.3  # Give 30% weight to new scores, 70% to historical
    
    profile = await profile_service.update_profile(
        user_id=user_id,
        new_scores=skill_scores,
        weight=weight,
        db=db
    )

    strengths_weaknesses = await profile_service.identify_strengths_weaknesses(profile)
    analysis_result.strengths = strengths_weaknesses.strengths
    analysis_result.weaknesses = strengths_weaknesses.weaknesses

    # Persist per-response feedback where relevant
    if response_type == "test":
        result_id = response_data.get("result_id")
        if result_id:
            result_row = await db.execute(
                select(UserTestResult).where(UserTestResult.id == int(result_id))
            )
            test_result = result_row.scalar_one_or_none()
            if test_result:
                test_result.ai_analysis = analysis_result.feedback
    elif response_type == "case":
        solution_id = response_data.get("solution_id")
        if solution_id:
            solution_row = await db.execute(
                select(CaseSolution).where(CaseSolution.id == int(solution_id))
            )
            case_solution = solution_row.scalar_one_or_none()
            if case_solution:
                case_solution.analysis_task_id = task_id
    
    logger.info(f"Profile updated for user {user_id}")
    
    # Step 5: Check if development plan generation is needed (Requirement 3.1)
    plan_service = PlanService()
    try:
        new_plan = await plan_service.check_and_generate_plan(
            user_id=user_id,
            profile=profile,
            db=db
        )

        if new_plan:
            logger.info(f"New development plan {new_plan.id} generated for user {user_id}")
    except Exception as e:
        logger.error(
            f"Plan generation failed after analysis task {task_id} (user_id={user_id}): {str(e)}",
            exc_info=True,
        )
    
    # Update task status to completed
    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    
    logger.info(f"Analysis task {task_id} completed successfully")


async def _mark_task_failed(
    task_id: str,
    error_message: str,
    db: AsyncSession
) -> None:
    """
    Mark an analysis task as failed and save error message.
    
    Requirements: 6.1
    """
    try:
        result = await db.execute(
            select(AnalysisTask).where(AnalysisTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if task:
            task.status = "failed"
            task.error_message = error_message
            task.retry_count += 1
            await db.commit()
            logger.info(f"Marked task {task_id} as failed (retry_count={task.retry_count})")
    except Exception as e:
        logger.error(f"Failed to mark task {task_id} as failed: {str(e)}")


async def generate_development_plan_background(
    user_id: int,
    profile_id: int
) -> None:
    """
    Background task to generate development plan.
    
    Steps:
    1. Get profile and history of plans
    2. Identify weaknesses
    3. Call LLMService to generate plan
    4. Archive previous plan
    5. Save new plan
    6. Handle errors with logging
    
    Args:
        user_id: User ID
        profile_id: Profile ID
        
    Requirements: 3.2, 3.3, 3.4, 3.5, 7.3
    """
    logger.info(
        f"Background plan generation task started: user_id={user_id}, "
        f"profile_id={profile_id}"
    )
    
    # Create a new database session for this background task
    async with AsyncSessionLocal() as db:
        try:
            # Use timeout for serverless compatibility (Requirement 6.1, 6.3)
            await asyncio.wait_for(
                _generate_plan_with_db(user_id, profile_id, db),
                timeout=30.0
            )
            
        except asyncio.TimeoutError:
            logger.error(f"Plan generation for user {user_id} timed out after 30 seconds")
            
        except Exception as e:
            logger.error(f"Error generating plan for user {user_id}: {str(e)}", exc_info=True)


async def _generate_plan_with_db(
    user_id: int,
    profile_id: int,
    db: AsyncSession
) -> None:
    """
    Internal function to generate plan with database session.
    
    Requirements: 3.2, 3.3, 3.4, 3.5, 7.3
    """
    # Step 1: Get profile
    result = await db.execute(
        select(SoftSkillsProfile).where(SoftSkillsProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        logger.error(f"Profile {profile_id} not found for user {user_id}")
        return
    
    # Step 2-6: Use PlanService to handle the rest
    plan_service = PlanService()
    
    new_plan = await plan_service.check_and_generate_plan(
        user_id=user_id,
        profile=profile,
        db=db
    )
    
    if new_plan:
        await db.commit()
        logger.info(f"Development plan {new_plan.id} generated successfully for user {user_id}")
    else:
        logger.info(f"No plan generation needed for user {user_id}")


async def retry_failed_analyses_background() -> None:
    """
    Background task to retry failed analyses.
    
    Finds all tasks with status="failed" and retry_count < 3,
    then retries processing them.
    
    This can be called periodically through a cron endpoint.
    
    Requirements: 6.1, 6.2
    """
    logger.info("Background retry task started for failed analyses")
    
    # Create a new database session for this background task
    async with AsyncSessionLocal() as db:
        try:
            # Find all failed tasks with retry_count < 3
            result = await db.execute(
                select(AnalysisTask).where(
                    and_(
                        AnalysisTask.status == "failed",
                        AnalysisTask.retry_count < 3
                    )
                )
            )
            failed_tasks = result.scalars().all()
            
            logger.info(f"Found {len(failed_tasks)} failed tasks to retry")
            
            for task in failed_tasks:
                logger.info(f"Retrying task {task.id} (attempt {task.retry_count + 1}/3)")
                
                # Reconstruct response_data based on response_type
                response_data = {}
                
                if task.response_type == "chat":
                    # Get the chat message
                    msg_result = await db.execute(
                        select(ChatMessage).where(ChatMessage.analysis_task_id == task.id)
                    )
                    chat_message = msg_result.scalar_one_or_none()
                    if chat_message:
                        response_data = {
                            "message": chat_message.message,
                            "response_id": chat_message.id
                        }
                elif task.response_type == "test":
                    result_row = await db.execute(
                        select(UserTestResult).where(UserTestResult.id == int(task.response_id))
                    )
                    test_result = result_row.scalar_one_or_none()
                    if test_result:
                        response_data = {
                            "test_id": test_result.test_id,
                            "result_id": test_result.id,
                            "answers": test_result.details or {}
                        }
                elif task.response_type == "case":
                    solution_row = await db.execute(
                        select(CaseSolution).where(CaseSolution.id == int(task.response_id))
                    )
                    case_solution = solution_row.scalar_one_or_none()
                    if case_solution:
                        response_data = {
                            "case_id": case_solution.test_id,
                            "solution_id": case_solution.id,
                            "solution": case_solution.solution
                        }
                
                # Reset task status to pending
                task.status = "pending"
                task.error_message = None
                await db.commit()
                
                # Retry processing
                try:
                    await asyncio.wait_for(
                        _process_analysis_with_db(
                            task.id,
                            task.user_id,
                            task.response_type,
                            response_data,
                            db
                        ),
                        timeout=30.0
                    )
                except Exception as e:
                    logger.error(f"Retry failed for task {task.id}: {str(e)}")
                    await _mark_task_failed(task.id, f"Retry failed: {str(e)}", db)
            
            logger.info("Retry task completed")
            
        except Exception as e:
            logger.error(f"Error in retry_failed_analyses_background: {str(e)}", exc_info=True)
