"""
Analysis Service for processing user responses and triggering background analysis.

This service coordinates the analysis of user responses (chat messages, test results,
case solutions) by creating analysis tasks and triggering background processing.
"""

import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import BackgroundTasks

from app.models.analysis import AnalysisTask, AnalysisResult
from app.models.chat import ChatMessage
from app.models.content import CaseSolution
from app.schemas.analysis import AnalysisStatus
from app.core.background import run_with_timeout_and_retry

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service for managing analysis of user responses"""
    
    def __init__(self):
        pass
    
    async def analyze_chat_message(
        self,
        user_id: int,
        message: str,
        db: AsyncSession,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> AnalysisTask:
        """
        Analyze a chat message and create an analysis task.
        
        Args:
            user_id: User ID
            message: Chat message text
            db: Database session
            background_tasks: FastAPI BackgroundTasks for async processing
            
        Returns:
            AnalysisTask with status "pending"
            
        Raises:
            ValueError: If message is too short (< 2 words)
            
        Requirements: 1.1, 6.4
        Property 1: Universal Analysis Triggering
        """
        # Validate input (Requirement 6.4)
        self._validate_chat_message(message)
        
        # Save chat message to database
        chat_message = ChatMessage(
            user_id=user_id,
            message=message,
            is_user=True
        )
        db.add(chat_message)
        await db.flush()
        await db.refresh(chat_message)
        
        # Create analysis task with status="pending" (Requirement 1.1)
        task_id = str(uuid.uuid4())
        analysis_task = AnalysisTask(
            id=task_id,
            user_id=user_id,
            response_type="chat",
            response_id=chat_message.id,
            status="pending",
            retry_count=0
        )
        db.add(analysis_task)
        
        # Link chat message to analysis task
        chat_message.analysis_task_id = task_id
        
        await db.commit()
        await db.refresh(analysis_task)
        
        # Schedule background processing if BackgroundTasks provided
        if background_tasks:
            from app.tasks.background_tasks import process_analysis_background
            background_tasks.add_task(
                process_analysis_background,
                task_id=task_id,
                user_id=user_id,
                response_type="chat",
                response_data={"message": message, "response_id": chat_message.id}
            )
            logger.info(f"Scheduled background analysis for chat message. Task ID: {task_id}")
        
        return analysis_task
    
    async def analyze_test_result(
        self,
        user_id: int,
        test_id: int,
        result_id: int,
        answers: Dict[str, Any],
        db: AsyncSession,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> AnalysisTask:
        """
        Analyze test results and create an analysis task.
        
        Args:
            user_id: User ID
            test_id: Test ID
            answers: User's answers to test questions
            db: Database session
            background_tasks: FastAPI BackgroundTasks for async processing
            
        Returns:
            AnalysisTask with status "pending"
            
        Raises:
            ValueError: If required fields are missing
            
        Requirements: 1.3, 6.4
        Property 1: Universal Analysis Triggering
        """
        # Validate input (Requirement 6.4)
        self._validate_test_answers(test_id, answers)
        
        # Create analysis task with status="pending" (Requirement 1.3)
        task_id = str(uuid.uuid4())
        analysis_task = AnalysisTask(
            id=task_id,
            user_id=user_id,
            response_type="test",
            response_id=result_id,
            status="pending",
            retry_count=0
        )
        db.add(analysis_task)
        await db.commit()
        await db.refresh(analysis_task)
        
        # Schedule background processing if BackgroundTasks provided
        if background_tasks:
            from app.tasks.background_tasks import process_analysis_background
            background_tasks.add_task(
                process_analysis_background,
                task_id=task_id,
                user_id=user_id,
                response_type="test",
                response_data={"test_id": test_id, "result_id": result_id, "answers": answers}
            )
            logger.info(f"Scheduled background analysis for test result. Task ID: {task_id}")
        
        return analysis_task
    
    async def analyze_case_solution(
        self,
        user_id: int,
        case_id: int,
        solution: str,
        solution_id: int,
        db: AsyncSession,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> AnalysisTask:
        """
        Analyze case solution and create an analysis task.
        
        Args:
            user_id: User ID
            case_id: Case ID
            solution: User's solution text
            db: Database session
            background_tasks: FastAPI BackgroundTasks for async processing
            
        Returns:
            AnalysisTask with status "pending"
            
        Raises:
            ValueError: If solution is too short (< 2 words)
            
        Requirements: 1.4, 6.4
        Property 1: Universal Analysis Triggering
        """
        # Validate input (Requirement 6.4)
        self._validate_message(solution)
        
        # Create analysis task with status="pending" (Requirement 1.4)
        task_id = str(uuid.uuid4())
        analysis_task = AnalysisTask(
            id=task_id,
            user_id=user_id,
            response_type="case",
            response_id=solution_id,
            status="pending",
            retry_count=0
        )
        db.add(analysis_task)

        if solution_id:
            solution_row = await db.execute(
                select(CaseSolution).where(CaseSolution.id == int(solution_id))
            )
            case_solution = solution_row.scalar_one_or_none()
            if case_solution:
                case_solution.analysis_task_id = task_id

        await db.commit()
        await db.refresh(analysis_task)
        
        # Schedule background processing if BackgroundTasks provided
        if background_tasks:
            from app.tasks.background_tasks import process_analysis_background
            background_tasks.add_task(
                process_analysis_background,
                task_id=task_id,
                user_id=user_id,
                response_type="case",
                response_data={"case_id": case_id, "solution_id": solution_id, "solution": solution}
            )
            logger.info(f"Scheduled background analysis for case solution. Task ID: {task_id}")
        
        return analysis_task
    
    async def get_analysis_status(
        self,
        task_id: str,
        db: AsyncSession
    ) -> AnalysisStatus:
        """
        Get the status of an analysis task.
        
        Args:
            task_id: Analysis task ID
            db: Database session
            
        Returns:
            AnalysisStatus with task status and result (if completed)
            
        Raises:
            ValueError: If task not found
            
        Requirements: 1.5, 6.3
        """
        # Get analysis task
        result = await db.execute(
            select(AnalysisTask).where(AnalysisTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if task is None:
            raise ValueError(f"Analysis task not found: {task_id}")
        
        # Get analysis result if task is completed
        analysis_result = None
        if task.status == "completed":
            result = await db.execute(
                select(AnalysisResult).where(AnalysisResult.task_id == task_id)
            )
            analysis_result = result.scalar_one_or_none()
        
        return AnalysisStatus(
            task_id=task_id,
            status=task.status,
            result=analysis_result
        )
    
    def _validate_message(self, message: str) -> None:
        """
        Validate that a message meets minimum requirements.
        
        Args:
            message: Message text to validate
            
        Raises:
            ValueError: If message is too short (< 2 words)
            
        Requirements: 6.4
        Property 20: Input Validation for Short Messages
        """
        if not message or not message.strip():
            raise ValueError("Сообщение не может быть пустым")

        # Check word count (must be at least 2 words)
        words = message.strip().split()
        if len(words) < 2:
            raise ValueError("Сообщение слишком короткое. Пожалуйста, напишите более развернутый ответ (минимум 2 слова)")

    def _validate_chat_message(self, message: str) -> None:
        if not message or not message.strip():
            raise ValueError("Сообщение не может быть пустым")
    
    def _validate_test_answers(self, test_id: int, answers: Dict[str, Any]) -> None:
        """
        Validate that test answers contain required fields.
        
        Args:
            test_id: Test ID
            answers: User's answers
            
        Raises:
            ValueError: If required fields are missing
            
        Requirements: 6.4
        """
        if not test_id or test_id <= 0:
            raise ValueError("Некорректный ID теста")
        
        if not answers or not isinstance(answers, dict):
            raise ValueError("Ответы на тест должны быть предоставлены")
        
        if len(answers) == 0:
            raise ValueError("Тест не содержит ответов")


# Create a singleton instance
analysis_service = AnalysisService()
