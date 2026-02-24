"""
LLM Service for analyzing user responses and generating development plans.
Uses Yandex GPT through LangChain for structured prompts and response parsing.
"""

import json
import logging
import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import deque
from langchain_community.chat_models import ChatYandexGPT
from app.core.config import settings
from app.core.logging_config import llm_call_logger
from app.schemas.analysis import SkillScores
from app.schemas.plan import DevelopmentPlanContent, MaterialItem, TaskItem, TestRecommendation
from app.models.profile import SoftSkillsProfile, DevelopmentPlan
import httpx
from requests.exceptions import ConnectionError, Timeout, RequestException

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Base exception for LLM service errors"""
    pass


class LLMUnavailableError(LLMServiceError):
    """Exception raised when LLM API is unavailable"""
    pass


class LLMRateLimitError(LLMServiceError):
    """Exception raised when LLM API rate limit is exceeded"""
    pass


class LLMInvalidResponseError(LLMServiceError):
    """Exception raised when LLM returns invalid response"""
    pass


class RateLimiter:
    """
    Simple in-memory rate limiter for LLM requests.
    
    Tracks request timestamps and enforces a maximum number of requests
    per time window (e.g., 60 requests per minute).
    """
    
    def __init__(self, max_requests: int = 60, time_window_seconds: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in time window
            time_window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = timedelta(seconds=time_window_seconds)
        self.request_timestamps: deque = deque()
        
    def check_rate_limit(self) -> bool:
        """
        Check if a new request would exceed the rate limit.
        
        Returns:
            bool: True if request is allowed, False if rate limit exceeded
        """
        now = datetime.utcnow()
        
        # Remove timestamps outside the time window
        while self.request_timestamps and self.request_timestamps[0] < now - self.time_window:
            self.request_timestamps.popleft()
        
        # Check if we're at the limit
        if len(self.request_timestamps) >= self.max_requests:
            logger.warning(
                f"Rate limit exceeded: {len(self.request_timestamps)} requests "
                f"in last {self.time_window.seconds} seconds"
            )
            return False
        
        return True
    
    def record_request(self) -> None:
        """Record a new request timestamp."""
        self.request_timestamps.append(datetime.utcnow())
    
    def get_wait_time(self) -> float:
        """
        Get the time to wait before the next request is allowed.
        
        Returns:
            float: Seconds to wait, or 0 if request is allowed now
        """
        if not self.request_timestamps:
            return 0.0
        
        now = datetime.utcnow()
        oldest_request = self.request_timestamps[0]
        time_since_oldest = (now - oldest_request).total_seconds()
        
        if time_since_oldest < self.time_window.seconds:
            return self.time_window.seconds - time_since_oldest
        
        return 0.0


# Prompt Templates
ANALYSIS_PROMPT = """
Ты - эксперт по оценке soft skills. Проанализируй следующий ответ пользователя.

КОНТЕКСТ: {context}

ОТВЕТ ПОЛЬЗОВАТЕЛЯ:
{user_response}

ЗАДАЧА:
Оцени следующие навыки по шкале от 0 до 100:
1. Коммуникация (communication)
2. Эмоциональный интеллект (emotional_intelligence)
3. Критическое мышление (critical_thinking)
4. Тайм-менеджмент (time_management)
5. Лидерство (leadership)

ВАЖНО: оценка должна быть строгой и доказательной.
- 90–100 ставь только при явных, конкретных примерах поведения и решений.
- 70–89 — выше среднего, если есть убедительные признаки навыка.
- 50–69 — средний уровень, если признаки слабые/частичные.
- 0–49 — ниже среднего или если навык не проявлен.
- Если в тексте НЕТ явных данных по навыку, не завышай: ставь низко/средне-низко.

ВАЖНО ДЛЯ ГОЛОСОВЫХ: текст может быть распознан из голосового сообщения.
Если по формулировкам заметны сарказм/ирония/пассивная агрессия, учитывай это в оценке (особенно communication и emotional_intelligence).

ФОРМАТ ОТВЕТА (строго JSON):
{{
    "communication": <число 0-100>,
    "emotional_intelligence": <число 0-100>,
    "critical_thinking": <число 0-100>,
    "time_management": <число 0-100>,
    "leadership": <число 0-100>,
    "feedback": "<краткий комментарий на русском>"
}}

Отвечай ТОЛЬКО в формате JSON, без дополнительного текста.
"""

PLAN_GENERATION_PROMPT = """
Ты - эксперт по развитию soft skills. Создай индивидуальную программу развития.

ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:
- Коммуникация: {communication_score}/100
- Эмоциональный интеллект: {emotional_intelligence_score}/100
- Критическое мышление: {critical_thinking_score}/100
- Тайм-менеджмент: {time_management_score}/100
- Лидерство: {leadership_score}/100

УРОВЕНЬ ПОЛЬЗОВАТЕЛЯ: {target_difficulty}

СЛАБЫЕ СТОРОНЫ: {weaknesses}

ПРЕДЫДУЩИЕ МАТЕРИАЛЫ (не повторять):
{previous_materials}

ЗАДАЧА:
Создай программу развития с:
1. 5-7 теоретических материалов (статьи, видео, курсы)
2. 3-5 практических заданий
3. 2-3 рекомендации по тестам/кейсам

ВАЖНО:
- Подбирай материалы и задания по уровню пользователя.
- Поле difficulty у материалов выставляй преимущественно как {target_difficulty}.
- Допускается смешивание уровней, но не больше 1-2 материалов выше уровня.

ФОРМАТ ОТВЕТА (строго JSON):
{{
    "materials": [
        {{
            "id": "<уникальный id>",
            "title": "<название>",
            "url": "<ссылка>",
            "type": "article|video|course",
            "skill": "<навык>",
            "difficulty": "beginner|intermediate|advanced"
        }}
    ],
    "tasks": [
        {{
            "id": "<уникальный id>",
            "description": "<описание задания>",
            "skill": "<навык>",
            "status": "pending",
            "completed_at": null
        }}
    ],
    "recommended_tests": [
        {{
            "test_id": <число>,
            "title": "<название теста>",
            "reason": "<почему рекомендуется>"
        }}
    ]
}}

Отвечай ТОЛЬКО в формате JSON, без дополнительного текста.
"""


class LLMService:
    """Service for interacting with Yandex GPT for analysis and plan generation."""
    
    MAX_RETRIES = 2  # Maximum number of retry attempts for invalid responses
    
    def __init__(self, enable_rate_limiting: bool = True, max_requests_per_minute: int = 60):
        """
        Initialize LLM service with Yandex GPT configuration.
        
        Args:
            enable_rate_limiting: Whether to enable rate limiting (default: True)
            max_requests_per_minute: Maximum requests per minute (default: 60)
        """
        self.folder_id = str(settings.YANDEX_FOLDER_ID or "").strip()
        self.api_key = str(settings.YANDEX_API_KEY or "").strip()
        self.llm_enabled = bool(self.folder_id and self.api_key)
        self.llm = None
        if self.llm_enabled:
            self.llm = ChatYandexGPT(
                folder_id=self.folder_id,
                api_key=self.api_key,
                model_uri=f"gpt://{self.folder_id}/yandexgpt-lite",
                temperature=0.6,
            )
        else:
            logger.warning("Yandex LLM config is incomplete. LLM calls will use graceful fallback.")
        
        # Initialize rate limiter
        self.enable_rate_limiting = enable_rate_limiting
        if self.enable_rate_limiting:
            self.rate_limiter = RateLimiter(
                max_requests=max_requests_per_minute,
                time_window_seconds=60
            )
            logger.info(f"Rate limiting enabled: {max_requests_per_minute} requests per minute")
        else:
            self.rate_limiter = None
            logger.info("Rate limiting disabled")
    
    def _check_rate_limit(self) -> None:
        """
        Check rate limit before making a request.
        
        Raises:
            LLMRateLimitError: If rate limit is exceeded
        """
        if not self.enable_rate_limiting or not self.rate_limiter:
            return
        
        if not self.rate_limiter.check_rate_limit():
            wait_time = self.rate_limiter.get_wait_time()
            raise LLMRateLimitError(
                f"Превышен лимит запросов к сервису анализа. "
                f"Пожалуйста, попробуйте снова через {int(wait_time)} секунд."
            )
    
    def _record_request(self) -> None:
        """Record a request for rate limiting."""
        if self.enable_rate_limiting and self.rate_limiter:
            self.rate_limiter.record_request()

    def _ensure_llm_available(self, method: str) -> None:
        if self.llm_enabled and self.llm is not None:
            return
        raise LLMUnavailableError(
            f"LLM backend is not configured for method '{method}'."
        )
    
    async def analyze_communication(
        self, 
        text: str, 
        context: Optional[str] = None
    ) -> SkillScores:
        """
        Analyze communication text and return skill scores.
        
        Args:
            text: User's text response to analyze
            context: Optional context about the conversation or scenario
            
        Returns:
            SkillScores: Scores for all 5 soft skills (0-100)
            
        Raises:
            LLMUnavailableError: If LLM API is unavailable
            LLMRateLimitError: If rate limit is exceeded
            LLMInvalidResponseError: If response cannot be parsed after retries
        """
        # Generate unique request ID for tracking
        request_id = str(uuid.uuid4())
        start_time = time.time()

        self._ensure_llm_available("analyze_communication")
        
        # Check rate limit before making request
        self._check_rate_limit()
        
        prompt = self._build_analysis_prompt(text, "communication", context)
        
        # Log the request
        llm_call_logger.log_request(
            request_id=request_id,
            method="analyze_communication",
            prompt=prompt,
            context={"text_length": len(text), "has_context": context is not None}
        )
        
        # Attempt with retry logic
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                # Record request for rate limiting
                self._record_request()
                
                response = self.llm.invoke(prompt)
                response_text = response.content
                
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000
                
                # Log the response
                llm_call_logger.log_response(
                    request_id=request_id,
                    method="analyze_communication",
                    response=response_text,
                    duration_ms=duration_ms,
                    success=True
                )
                
                # Parse and validate the response
                parsed_data = self._parse_llm_response(response_text, "skill_scores")
                parsed_data = self._calibrate_free_text_scores(parsed_data, text)
                
                # Create SkillScores object
                skill_scores = SkillScores(
                    communication=parsed_data.get("communication", 0),
                    emotional_intelligence=parsed_data.get("emotional_intelligence", 0),
                    critical_thinking=parsed_data.get("critical_thinking", 0),
                    time_management=parsed_data.get("time_management", 0),
                    leadership=parsed_data.get("leadership", 0),
                    feedback=parsed_data.get("feedback")
                )
                
                logger.info(f"Successfully analyzed communication text on attempt {attempt + 1}. Scores: {skill_scores}")
                return skill_scores
                
            except (ConnectionError, Timeout, httpx.ConnectError, httpx.TimeoutException) as e:
                # LLM API is unavailable - graceful degradation
                duration_ms = (time.time() - start_time) * 1000
                llm_call_logger.log_error(request_id, "analyze_communication", e, duration_ms)
                
                logger.error(f"LLM API unavailable on attempt {attempt + 1}: {str(e)}")
                if attempt >= self.MAX_RETRIES:
                    raise LLMUnavailableError(
                        "Сервис анализа временно недоступен. "
                        "Ваш ответ сохранен и будет обработан позже. "
                        "Пожалуйста, попробуйте снова через несколько минут."
                    )
                # Wait before retry (exponential backoff)
                import asyncio
                await asyncio.sleep(2 ** attempt)
                
            except ValueError as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.warning(f"Attempt {attempt + 1}/{self.MAX_RETRIES + 1} failed to parse LLM response: {e}")
                
                if attempt < self.MAX_RETRIES:
                    # Refine prompt for retry
                    prompt = self._refine_prompt_for_retry(prompt, str(e), "skill_scores")
                    logger.info(f"Retrying with refined prompt (attempt {attempt + 2}/{self.MAX_RETRIES + 1})")
                else:
                    # Max retries exceeded
                    llm_call_logger.log_error(request_id, "analyze_communication", e, duration_ms)
                    logger.error(f"Failed to analyze communication after {self.MAX_RETRIES + 1} attempts. Last error: {e}")
                    raise LLMInvalidResponseError(
                        "Не удалось обработать ответ от сервиса анализа. "
                        "Ваш ответ сохранен и будет обработан позже."
                    )
                    
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                llm_call_logger.log_error(request_id, "analyze_communication", e, duration_ms)
                
                error_str = str(e).lower()
                # Check for rate limiting
                if "rate limit" in error_str or "429" in error_str or "quota" in error_str:
                    logger.error(f"Rate limit exceeded on attempt {attempt + 1}: {e}")
                    raise LLMRateLimitError(
                        "Превышен лимит запросов к сервису анализа. "
                        "Пожалуйста, попробуйте снова через минуту."
                    )
                
                logger.error(f"Unexpected error analyzing communication on attempt {attempt + 1}: {e}")
                if attempt >= self.MAX_RETRIES:
                    raise LLMUnavailableError(
                        "Произошла ошибка при анализе. "
                        "Ваш ответ сохранен и будет обработан позже."
                    )
    
    async def analyze_test_answers(
        self, 
        test_type: str, 
        questions: List[Dict[str, Any]], 
        answers: Dict[str, Any]
    ) -> SkillScores:
        """
        Analyze test answers and return skill scores.
        
        Args:
            test_type: Type of test (e.g., 'emotional_intelligence', 'leadership')
            questions: List of test questions with their details
            answers: User's answers to the test questions
            
        Returns:
            SkillScores: Scores for all 5 soft skills (0-100)
            
        Raises:
            LLMUnavailableError: If LLM API is unavailable
            LLMRateLimitError: If rate limit is exceeded
            LLMInvalidResponseError: If response cannot be parsed after retries
        """
        # Generate unique request ID for tracking
        request_id = str(uuid.uuid4())
        start_time = time.time()

        self._ensure_llm_available("analyze_test_answers")
        
        # Check rate limit before making request
        self._check_rate_limit()
        
        prompt = self._build_test_analysis_prompt(test_type, questions, answers)
        
        # Log the request
        llm_call_logger.log_request(
            request_id=request_id,
            method="analyze_test_answers",
            prompt=prompt,
            context={
                "test_type": test_type,
                "num_questions": len(questions),
                "num_answers": len(answers)
            }
        )
        
        # Attempt with retry logic
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                # Record request for rate limiting
                self._record_request()
                
                response = self.llm.invoke(prompt)
                response_text = response.content
                
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000
                
                # Log the response
                llm_call_logger.log_response(
                    request_id=request_id,
                    method="analyze_test_answers",
                    response=response_text,
                    duration_ms=duration_ms,
                    success=True
                )
                
                # Parse and validate the response
                parsed_data = self._parse_llm_response(response_text, "skill_scores")
                parsed_data = self._calibrate_test_scores(parsed_data, questions, answers)
                
                # Create SkillScores object
                skill_scores = SkillScores(
                    communication=parsed_data.get("communication", 0),
                    emotional_intelligence=parsed_data.get("emotional_intelligence", 0),
                    critical_thinking=parsed_data.get("critical_thinking", 0),
                    time_management=parsed_data.get("time_management", 0),
                    leadership=parsed_data.get("leadership", 0),
                    feedback=parsed_data.get("feedback")
                )
                
                logger.info(f"Successfully analyzed test answers for {test_type} on attempt {attempt + 1}. Scores: {skill_scores}")
                return skill_scores
                
            except (ConnectionError, Timeout, httpx.ConnectError, httpx.TimeoutException) as e:
                # LLM API is unavailable - graceful degradation
                duration_ms = (time.time() - start_time) * 1000
                llm_call_logger.log_error(request_id, "analyze_test_answers", e, duration_ms)
                
                logger.error(f"LLM API unavailable on attempt {attempt + 1}: {str(e)}")
                if attempt >= self.MAX_RETRIES:
                    raise LLMUnavailableError(
                        "Сервис анализа временно недоступен. "
                        "Ваш ответ сохранен и будет обработан позже. "
                        "Пожалуйста, попробуйте снова через несколько минут."
                    )
                # Wait before retry (exponential backoff)
                import asyncio
                await asyncio.sleep(2 ** attempt)
                
            except ValueError as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.warning(f"Attempt {attempt + 1}/{self.MAX_RETRIES + 1} failed to parse LLM response: {e}")
                
                if attempt < self.MAX_RETRIES:
                    # Refine prompt for retry
                    prompt = self._refine_prompt_for_retry(prompt, str(e), "skill_scores")
                    logger.info(f"Retrying with refined prompt (attempt {attempt + 2}/{self.MAX_RETRIES + 1})")
                else:
                    # Max retries exceeded
                    llm_call_logger.log_error(request_id, "analyze_test_answers", e, duration_ms)
                    logger.error(f"Failed to analyze test answers after {self.MAX_RETRIES + 1} attempts. Last error: {e}")
                    raise LLMInvalidResponseError(
                        "Не удалось обработать ответ от сервиса анализа. "
                        "Ваш ответ сохранен и будет обработан позже."
                    )
                    
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                llm_call_logger.log_error(request_id, "analyze_test_answers", e, duration_ms)
                
                error_str = str(e).lower()
                # Check for rate limiting
                if "rate limit" in error_str or "429" in error_str or "quota" in error_str:
                    logger.error(f"Rate limit exceeded on attempt {attempt + 1}: {e}")
                    raise LLMRateLimitError(
                        "Превышен лимит запросов к сервису анализа. "
                        "Пожалуйста, попробуйте снова через минуту."
                    )
                
                logger.error(f"Unexpected error analyzing test answers on attempt {attempt + 1}: {e}")
                if attempt >= self.MAX_RETRIES:
                    raise LLMUnavailableError(
                        "Произошла ошибка при анализе. "
                        "Ваш ответ сохранен и будет обработан позже."
                    )
    
    async def generate_development_plan(
        self, 
        profile: SoftSkillsProfile, 
        weaknesses: List[str], 
        history: List[DevelopmentPlan]
    ) -> DevelopmentPlanContent:
        """
        Generate a personalized development plan based on user's profile and weaknesses.
        
        Args:
            profile: User's current soft skills profile
            weaknesses: List of identified weak skills
            history: List of previous development plans to avoid repetition
            
        Returns:
            DevelopmentPlanContent: Generated development plan with materials, tasks, and recommendations
            
        Raises:
            LLMUnavailableError: If LLM API is unavailable
            LLMRateLimitError: If rate limit is exceeded
            LLMInvalidResponseError: If response cannot be parsed after retries
        """
        # Generate unique request ID for tracking
        request_id = str(uuid.uuid4())
        start_time = time.time()

        self._ensure_llm_available("generate_development_plan")
        
        # Check rate limit before making request
        self._check_rate_limit()
        
        prompt = self._build_plan_generation_prompt(profile, weaknesses, history)
        
        # Log the request
        llm_call_logger.log_request(
            request_id=request_id,
            method="generate_development_plan",
            prompt=prompt,
            context={
                "user_id": profile.user_id,
                "weaknesses": weaknesses,
                "num_previous_plans": len(history)
            }
        )
        
        # Attempt with retry logic
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                # Record request for rate limiting
                self._record_request()
                
                response = self.llm.invoke(prompt)
                response_text = response.content
                
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000
                
                # Log the response
                llm_call_logger.log_response(
                    request_id=request_id,
                    method="generate_development_plan",
                    response=response_text,
                    duration_ms=duration_ms,
                    success=True
                )
                
                # Parse and validate the response
                parsed_data = self._parse_llm_response(response_text, "development_plan")
                
                # Create DevelopmentPlanContent object
                materials = [
                    MaterialItem(**material) 
                    for material in parsed_data.get("materials", [])
                ]
                
                tasks = [
                    TaskItem(**task) 
                    for task in parsed_data.get("tasks", [])
                ]
                
                recommended_tests = [
                    TestRecommendation(**test) 
                    for test in parsed_data.get("recommended_tests", [])
                ]
                
                plan_content = DevelopmentPlanContent(
                    weaknesses=weaknesses,
                    materials=materials,
                    tasks=tasks,
                    recommended_tests=recommended_tests
                )
                
                logger.info(f"Successfully generated development plan on attempt {attempt + 1} with {len(materials)} materials and {len(tasks)} tasks")
                return plan_content
                
            except (ConnectionError, Timeout, httpx.ConnectError, httpx.TimeoutException) as e:
                # LLM API is unavailable - graceful degradation
                duration_ms = (time.time() - start_time) * 1000
                llm_call_logger.log_error(request_id, "generate_development_plan", e, duration_ms)
                
                logger.error(f"LLM API unavailable on attempt {attempt + 1}: {str(e)}")
                if attempt >= self.MAX_RETRIES:
                    raise LLMUnavailableError(
                        "Сервис генерации программы развития временно недоступен. "
                        "Пожалуйста, попробуйте снова через несколько минут."
                    )
                # Wait before retry (exponential backoff)
                import asyncio
                await asyncio.sleep(2 ** attempt)
                
            except ValueError as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.warning(f"Attempt {attempt + 1}/{self.MAX_RETRIES + 1} failed to parse LLM response: {e}")
                
                if attempt < self.MAX_RETRIES:
                    # Refine prompt for retry
                    prompt = self._refine_prompt_for_retry(prompt, str(e), "development_plan")
                    logger.info(f"Retrying with refined prompt (attempt {attempt + 2}/{self.MAX_RETRIES + 1})")
                else:
                    # Max retries exceeded
                    llm_call_logger.log_error(request_id, "generate_development_plan", e, duration_ms)
                    logger.error(f"Failed to generate development plan after {self.MAX_RETRIES + 1} attempts. Last error: {e}")
                    raise LLMInvalidResponseError(
                        "Не удалось сгенерировать программу развития. "
                        "Пожалуйста, попробуйте снова позже."
                    )
                    
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                llm_call_logger.log_error(request_id, "generate_development_plan", e, duration_ms)
                
                error_str = str(e).lower()
                # Check for rate limiting
                if "rate limit" in error_str or "429" in error_str or "quota" in error_str:
                    logger.error(f"Rate limit exceeded on attempt {attempt + 1}: {e}")
                    raise LLMRateLimitError(
                        "Превышен лимит запросов к сервису генерации. "
                        "Пожалуйста, попробуйте снова через минуту."
                    )
                
                logger.error(f"Unexpected error generating development plan on attempt {attempt + 1}: {e}")
                if attempt >= self.MAX_RETRIES:
                    raise LLMUnavailableError(
                        "Произошла ошибка при генерации программы развития. "
                        "Пожалуйста, попробуйте снова позже."
                    )
    
    def _build_analysis_prompt(
        self, 
        text: str, 
        analysis_type: str, 
        context: Optional[str] = None
    ) -> str:
        """
        Build a structured prompt for analyzing user text.
        
        Args:
            text: User's text to analyze
            analysis_type: Type of analysis (e.g., 'communication', 'case')
            context: Optional context information
            
        Returns:
            str: Formatted prompt for LLM
        """
        context_text = context if context else "Общий анализ ответа пользователя"
        
        prompt = ANALYSIS_PROMPT.format(
            context=context_text,
            user_response=text
        )
        
        return prompt
    
    def _build_test_analysis_prompt(
        self, 
        test_type: str, 
        questions: List[Dict[str, Any]], 
        answers: Dict[str, Any]
    ) -> str:
        """
        Build a structured prompt for analyzing test answers.
        
        Args:
            test_type: Type of test
            questions: List of questions
            answers: User's answers
            
        Returns:
            str: Formatted prompt for LLM
        """
        # Format questions and answers for the prompt
        qa_text = ""
        for i, question in enumerate(questions):
            q_id = question.get("id", i)
            q_text = question.get("text", "")
            answer = answers.get(str(q_id), "Не отвечено")
            qa_text += f"\nВопрос {i+1}: {q_text}\nОтвет: {answer}\n"
        
        prompt = f"""Ты - эксперт по оценке soft skills. Проанализируй ответы пользователя на тест "{test_type}".

ВОПРОСЫ И ОТВЕТЫ:
{qa_text}

ЗАДАЧА:
Оцени следующие навыки по шкале от 0 до 100 на основе ответов.

ВАЖНО: оценка должна быть строгой и доказательной.
- 90–100 ставь только за выдающиеся ответы с ясной аргументацией и примерами.
- 70–89 — выше среднего, когда ответы уверенные и содержательные.
- 50–69 — средний уровень, если ответы поверхностные или неоднозначные.
- 0–49 — ниже среднего при слабых/ошибочных ответах.
- Если сомневаешься, занижай оценку, а не завышай.

1. Коммуникация (communication)
2. Эмоциональный интеллект (emotional_intelligence)
3. Критическое мышление (critical_thinking)
4. Тайм-менеджмент (time_management)
5. Лидерство (leadership)

ФОРМАТ ОТВЕТА (строго JSON):
{{
    "communication": <число 0-100>,
    "emotional_intelligence": <число 0-100>,
    "critical_thinking": <число 0-100>,
    "time_management": <число 0-100>,
    "leadership": <число 0-100>,
    "feedback": "<краткий комментарий на русском>"
}}

Отвечай ТОЛЬКО в формате JSON, без дополнительного текста."""
        
        return prompt
    
    def _build_plan_generation_prompt(
        self, 
        profile: SoftSkillsProfile, 
        weaknesses: List[str], 
        history: List[DevelopmentPlan]
    ) -> str:
        """
        Build a structured prompt for generating a development plan.
        
        Args:
            profile: User's soft skills profile
            weaknesses: List of weak skills
            history: Previous development plans
            
        Returns:
            str: Formatted prompt for LLM
        """
        # Extract previous materials to avoid repetition
        previous_materials = []
        for plan in history:
            if plan.content and isinstance(plan.content, dict):
                materials = plan.content.get("materials", [])
                previous_materials.extend([m.get("title", "") for m in materials])
        
        previous_materials_text = "\n".join(previous_materials) if previous_materials else "Нет предыдущих материалов"
        weaknesses_text = ", ".join(weaknesses) if weaknesses else "Не определены"

        avg_score = (
            float(profile.communication_score or 0.0)
            + float(profile.emotional_intelligence_score or 0.0)
            + float(profile.critical_thinking_score or 0.0)
            + float(profile.time_management_score or 0.0)
            + float(profile.leadership_score or 0.0)
        ) / 5.0
        if avg_score >= 70:
            target_difficulty = "advanced"
        elif avg_score >= 40:
            target_difficulty = "intermediate"
        else:
            target_difficulty = "beginner"
        
        prompt = PLAN_GENERATION_PROMPT.format(
            communication_score=profile.communication_score,
            emotional_intelligence_score=profile.emotional_intelligence_score,
            critical_thinking_score=profile.critical_thinking_score,
            time_management_score=profile.time_management_score,
            leadership_score=profile.leadership_score,
            target_difficulty=target_difficulty,
            weaknesses=weaknesses_text,
            previous_materials=previous_materials_text
        )
        
        return prompt
    
    def _parse_llm_response(
        self, 
        response: str, 
        expected_format: str
    ) -> Dict[str, Any]:
        """
        Parse and validate LLM response.
        
        Args:
            response: Raw response text from LLM
            expected_format: Expected format type ('skill_scores' or 'development_plan')
            
        Returns:
            Dict[str, Any]: Parsed JSON data
            
        Raises:
            ValueError: If response cannot be parsed or is invalid
        """
        try:
            # Try to extract JSON from response
            # Sometimes LLM adds extra text, so we need to find the JSON part
            response = response.strip()
            
            # Find JSON object boundaries
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            
            if start_idx == -1 or end_idx == -1:
                raise ValueError("No JSON object found in response")
            
            json_str = response[start_idx:end_idx + 1]
            parsed_data = json.loads(json_str)
            
            # Validate based on expected format
            if expected_format == "skill_scores":
                self._validate_skill_scores(parsed_data)
            elif expected_format == "development_plan":
                self._validate_development_plan(parsed_data)
            
            return parsed_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM response: {e}")
            logger.error(f"Response was: {response}")
            raise ValueError(f"Invalid JSON in LLM response: {str(e)}")
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            raise ValueError(f"Failed to parse LLM response: {str(e)}")
    
    def _refine_prompt_for_retry(
        self,
        original_prompt: str,
        error_message: str,
        expected_format: str
    ) -> str:
        """
        Refine the prompt based on the error encountered to improve retry success.
        
        Args:
            original_prompt: The original prompt that failed
            error_message: The error message from the failed attempt
            expected_format: Expected format type ('skill_scores' or 'development_plan')
            
        Returns:
            str: Refined prompt with additional clarifications
        """
        # Add specific refinements based on error type
        refinement = "\n\n⚠️ ВАЖНО: Предыдущая попытка не удалась. "
        
        if "JSON" in error_message or "json" in error_message.lower():
            refinement += """Убедись, что твой ответ:
1. Содержит ТОЛЬКО валидный JSON объект
2. Не содержит дополнительного текста до или после JSON
3. Все строки заключены в двойные кавычки
4. Все числа указаны без кавычек
5. Нет лишних запятых в конце списков или объектов"""
        
        elif "Missing required" in error_message:
            # Extract which field is missing
            if expected_format == "skill_scores":
                refinement += """Убедись, что JSON содержит ВСЕ 5 обязательных полей:
- "communication" (число 0-100)
- "emotional_intelligence" (число 0-100)
- "critical_thinking" (число 0-100)
- "time_management" (число 0-100)
- "leadership" (число 0-100)
- "feedback" (строка с комментарием)"""
            elif expected_format == "development_plan":
                refinement += """Убедись, что JSON содержит ВСЕ обязательные поля:
- "materials" (массив объектов с полями: id, title, url, type, skill, difficulty)
- "tasks" (массив объектов с полями: id, description, skill, status, completed_at)
- "recommended_tests" (массив объектов с полями: test_id, title, reason)"""
        
        elif "Invalid score type" in error_message or "out of range" in error_message:
            refinement += """Убедись, что все оценки навыков:
1. Являются числами (не строками)
2. Находятся в диапазоне от 0 до 100
3. Не содержат специальных символов или текста"""
        
        else:
            refinement += """Внимательно проверь формат ответа и убедись, что он точно соответствует требованиям.
Ответ должен быть валидным JSON без дополнительного текста."""
        
        # Append refinement to original prompt
        refined_prompt = original_prompt + refinement
        
        logger.debug(f"Refined prompt with additional instructions based on error: {error_message}")
        return refined_prompt

    def _calibrate_test_scores(
        self,
        data: Dict[str, Any],
        questions: List[Dict[str, Any]],
        answers: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply conservative calibration to test scores to avoid inflated results.
        Compress high-end scores and mildly penalize incomplete answers.
        """
        calibrated = dict(data)
        total_questions = len(questions) if questions else len(answers)
        answered_count = 0

        if questions:
            for question in questions:
                q_id = str(question.get("id"))
                value = answers.get(q_id)
                if value is None:
                    continue
                if isinstance(value, str) and value.strip().lower() in {"", "не отвечено", "no answer"}:
                    continue
                answered_count += 1
        else:
            for value in answers.values():
                if value is None:
                    continue
                if isinstance(value, str) and value.strip().lower() in {"", "не отвечено", "no answer"}:
                    continue
                answered_count += 1

        coverage = answered_count / total_questions if total_questions else 1.0
        coverage_factor = 0.85 + 0.15 * coverage

        for key in [
            "communication",
            "emotional_intelligence",
            "critical_thinking",
            "time_management",
            "leadership",
        ]:
            raw = float(calibrated.get(key, 0))
            if raw > 70:
                raw = 70 + (raw - 70) * 0.5
            raw *= coverage_factor
            calibrated[key] = max(0.0, min(100.0, raw))

        return calibrated

    def _calibrate_free_text_scores(
        self,
        data: Dict[str, Any],
        text: str,
    ) -> Dict[str, Any]:
        calibrated = dict(data)

        raw_text = str(text or "")
        lowered = raw_text.lower()
        word_count = len([w for w in lowered.split() if w.strip()])

        tm_keywords = [
            "план",
            "планир",
            "дедлайн",
            "срок",
            "приорит",
            "распис",
            "календар",
            "задач",
            "тайм",
            "времен",
            "успева",
        ]
        leadership_keywords = [
            "команд",
            "руковод",
            "лидер",
            "делег",
            "ответствен",
            "инициатив",
            "мотивир",
            "управлен",
        ]

        tm_evidence = any(k in lowered for k in tm_keywords)
        leadership_evidence = any(k in lowered for k in leadership_keywords)

        # General conservative compression for free-text.
        for key in [
            "communication",
            "emotional_intelligence",
            "critical_thinking",
            "time_management",
            "leadership",
        ]:
            try:
                raw = float(calibrated.get(key, 0))
            except Exception:
                raw = 0.0

            if raw > 70:
                raw = 70 + (raw - 70) * 0.4

            if word_count < 25:
                raw *= 0.85

            calibrated[key] = max(0.0, min(100.0, raw))

        # Skill-specific caps if there's no evidence in text.
        if not tm_evidence:
            calibrated["time_management"] = min(float(calibrated.get("time_management", 0.0)), 50.0)

        if not leadership_evidence:
            calibrated["leadership"] = min(float(calibrated.get("leadership", 0.0)), 50.0)

        return calibrated
    
    def _validate_skill_scores(self, data: Dict[str, Any]) -> None:
        """
        Validate that skill scores response contains all required fields.
        
        Args:
            data: Parsed JSON data
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        required_skills = [
            "communication",
            "emotional_intelligence",
            "critical_thinking",
            "time_management",
            "leadership"
        ]
        
        for skill in required_skills:
            if skill not in data:
                raise ValueError(f"Missing required skill score: {skill}")
            
            score = data[skill]
            if not isinstance(score, (int, float)):
                raise ValueError(f"Invalid score type for {skill}: expected number, got {type(score)}")
            
            if not (0 <= score <= 100):
                logger.warning(f"Score for {skill} out of range: {score}. Clamping to [0, 100]")
                data[skill] = max(0, min(100, score))
    
    def _validate_development_plan(self, data: Dict[str, Any]) -> None:
        """
        Validate that development plan response contains all required fields.
        
        Args:
            data: Parsed JSON data
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        required_fields = ["materials", "tasks", "recommended_tests"]
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field in development plan: {field}")
            
            if not isinstance(data[field], list):
                raise ValueError(f"Field {field} must be a list")
        
        # Validate materials structure
        for material in data["materials"]:
            required_material_fields = ["id", "title", "url", "type", "skill", "difficulty"]
            for field in required_material_fields:
                if field not in material:
                    raise ValueError(f"Missing required field in material: {field}")
        
        # Validate tasks structure
        for task in data["tasks"]:
            required_task_fields = ["id", "description", "skill"]
            for field in required_task_fields:
                if field not in task:
                    raise ValueError(f"Missing required field in task: {field}")
            
            # Set default status if not present
            if "status" not in task:
                task["status"] = "pending"
            if "completed_at" not in task:
                task["completed_at"] = None
        
        # Validate recommended tests structure
        for test in data["recommended_tests"]:
            required_test_fields = ["test_id", "title", "reason"]
            for field in required_test_fields:
                if field not in test:
                    raise ValueError(f"Missing required field in recommended test: {field}")


# Create a singleton instance
llm_service = LLMService()
