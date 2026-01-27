"""
Background task utilities for serverless deployment.

This module provides utilities for running background tasks using FastAPI's
BackgroundTasks instead of Celery, which is more suitable for serverless
platforms like Vercel, Render, and Railway.
"""

import asyncio
import logging
from typing import Coroutine, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


async def run_with_timeout(
    coro: Coroutine[Any, Any, Any],
    timeout: int = 30,
    task_name: str = "background_task"
) -> Optional[Any]:
    """
    Run a coroutine with a timeout for serverless platform limits.
    
    Most serverless platforms have execution time limits (10-60 seconds).
    This function ensures tasks don't exceed those limits.
    
    Args:
        coro: The coroutine to execute
        timeout: Maximum execution time in seconds (default: 30)
        task_name: Name of the task for logging purposes
        
    Returns:
        The result of the coroutine if successful, None if timeout occurs
        
    Example:
        result = await run_with_timeout(
            some_async_function(),
            timeout=30,
            task_name="analyze_message"
        )
    """
    try:
        logger.info(f"Starting background task: {task_name}")
        start_time = datetime.utcnow()
        
        result = await asyncio.wait_for(coro, timeout=timeout)
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Background task '{task_name}' completed in {elapsed:.2f}s")
        
        return result
        
    except asyncio.TimeoutError:
        logger.warning(
            f"Background task '{task_name}' exceeded timeout of {timeout}s. "
            "Task will be saved for retry."
        )
        return None
        
    except Exception as e:
        logger.error(
            f"Background task '{task_name}' failed with error: {str(e)}",
            exc_info=True
        )
        raise


async def run_with_retry(
    coro_factory: callable,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    task_name: str = "background_task"
) -> Optional[Any]:
    """
    Run a coroutine with automatic retry logic.
    
    Useful for operations that may fail due to temporary issues like
    network errors or API rate limits.
    
    Args:
        coro_factory: A callable that returns a coroutine (not the coroutine itself)
        max_retries: Maximum number of retry attempts (default: 3)
        retry_delay: Delay between retries in seconds (default: 2.0)
        task_name: Name of the task for logging purposes
        
    Returns:
        The result of the coroutine if successful, None if all retries fail
        
    Example:
        result = await run_with_retry(
            lambda: llm_service.analyze(text),
            max_retries=3,
            task_name="llm_analysis"
        )
    """
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries} for task: {task_name}")
            
            coro = coro_factory()
            result = await coro
            
            logger.info(f"Task '{task_name}' succeeded on attempt {attempt + 1}")
            return result
            
        except Exception as e:
            last_exception = e
            logger.warning(
                f"Task '{task_name}' failed on attempt {attempt + 1}/{max_retries}: {str(e)}"
            )
            
            if attempt < max_retries - 1:
                # Exponential backoff
                delay = retry_delay * (2 ** attempt)
                logger.info(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)
    
    logger.error(
        f"Task '{task_name}' failed after {max_retries} attempts. "
        f"Last error: {str(last_exception)}"
    )
    return None


async def run_with_timeout_and_retry(
    coro_factory: callable,
    timeout: int = 30,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    task_name: str = "background_task"
) -> Optional[Any]:
    """
    Combine timeout and retry logic for robust background task execution.
    
    This is the recommended function for most background tasks in serverless
    environments, as it handles both timeout limits and transient failures.
    
    Args:
        coro_factory: A callable that returns a coroutine
        timeout: Maximum execution time per attempt in seconds (default: 30)
        max_retries: Maximum number of retry attempts (default: 3)
        retry_delay: Base delay between retries in seconds (default: 2.0)
        task_name: Name of the task for logging purposes
        
    Returns:
        The result of the coroutine if successful, None if all attempts fail
        
    Example:
        result = await run_with_timeout_and_retry(
            lambda: llm_service.analyze_and_save(user_id, message),
            timeout=30,
            max_retries=2,
            task_name="analyze_chat_message"
        )
    """
    async def wrapped_coro():
        coro = coro_factory()
        return await run_with_timeout(coro, timeout=timeout, task_name=task_name)
    
    return await run_with_retry(
        wrapped_coro,
        max_retries=max_retries,
        retry_delay=retry_delay,
        task_name=task_name
    )


class BackgroundTaskLogger:
    """
    Context manager for structured logging of background tasks.
    
    Automatically logs task start, completion, duration, and any errors.
    
    Example:
        async with BackgroundTaskLogger("analyze_message", user_id=123):
            result = await analyze_message(user_id, message)
    """
    
    def __init__(self, task_name: str, **context):
        self.task_name = task_name
        self.context = context
        self.start_time = None
        
    async def __aenter__(self):
        self.start_time = datetime.utcnow()
        context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
        logger.info(f"Starting task '{self.task_name}' with context: {context_str}")
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        
        if exc_type is None:
            logger.info(f"Task '{self.task_name}' completed successfully in {elapsed:.2f}s")
        else:
            logger.error(
                f"Task '{self.task_name}' failed after {elapsed:.2f}s: {exc_val}",
                exc_info=(exc_type, exc_val, exc_tb)
            )
        
        return False  # Don't suppress exceptions
