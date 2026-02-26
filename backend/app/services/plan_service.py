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
from app.models.content import Test, Question, UserTestResult, CaseSolution
from app.schemas.plan import DevelopmentPlanContent, MaterialItem, TaskItem, TestRecommendation
from app.services.llm_service import LLMService
from app.core.config import settings

logger = logging.getLogger(__name__)


class PlanService:
    """Service for managing development plans and their lifecycle."""
    
    def __init__(self):
        self.llm_service = LLMService()

    def _skill_keywords(self) -> Dict[str, List[str]]:
        return {
            "communication": [
                "Р С”Р С•Р СР СРЎС“Р Р…Р С‘Р С”",
                "Р С•Р В±РЎвЂ°Р ВµР Р…",
                "Р С—Р ВµРЎР‚Р ВµР С–Р С•Р Р†Р С•РЎР‚",
                "Р Т‘Р С‘Р В°Р В»Р С•Р С–",
                "communication",
                "conversation",
            ],
            "emotional_intelligence": [
                "РЎРЊР СР С•РЎвЂ Р С‘Р С•Р Р…",
                "РЎРЊР СР С—Р В°РЎвЂљ",
                "emotional",
                "intelligence",
                "ei",
            ],
            "critical_thinking": [
                "Р С”РЎР‚Р С‘РЎвЂљ",
                "Р СРЎвЂ№РЎв‚¬Р В»Р ВµР Р…",
                "Р В»Р С•Р С–Р С‘Р С”",
                "Р В°РЎР‚Р С–РЎС“Р СР ВµР Р…РЎвЂљ",
                "critical",
                "thinking",
            ],
            "time_management": [
                "РЎвЂљР В°Р в„–Р С",
                "Р Р†РЎР‚Р ВµР СР ВµР Р…",
                "Р Т‘Р ВµР Т‘Р В»Р В°Р в„–Р Р…",
                "Р С—РЎР‚Р С‘Р С•РЎР‚Р С‘РЎвЂљР ВµРЎвЂљ",
                "time",
                "management",
            ],
            "leadership": [
                "Р В»Р С‘Р Т‘Р ВµРЎР‚",
                "Р С”Р С•Р СР В°Р Р…Р Т‘",
                "Р Р†Р В»Р С‘РЎРЏР Р…Р С‘",
                "leadership",
                "lead",
            ],
        }

    def _normalize_text(self, value: Any) -> str:
        return str(value or "").strip().lower()

    def _strip_final_marker(self, value: str) -> str:
        text = str(value or "")
        cleaned = text.replace("[FINAL]", "").replace("[final]", "").strip()
        return " ".join(cleaned.split())

    def _normalize_difficulty(self, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        if normalized == "advanced":
            return "advanced"
        if normalized == "intermediate":
            return "intermediate"
        return "beginner"

    def _final_test_title(self, target_difficulty: str) -> str:
        normalized = self._normalize_difficulty(target_difficulty)
        return f"РС‚РѕРіРѕРІС‹Р№ С‚РµСЃС‚ ({normalized})"

    def _legacy_final_test_title(self, target_difficulty: str) -> str:
        normalized = self._normalize_difficulty(target_difficulty)
        return f"[FINAL] РС‚РѕРіРѕРІС‹Р№ С‚РµСЃС‚ ({normalized})"

    def _final_simulation_title(self, target_difficulty: str) -> str:
        normalized = self._normalize_difficulty(target_difficulty)
        return f"РС‚РѕРіРѕРІР°СЏ СЂРѕР»РµРІР°СЏ РёРіСЂР° ({normalized})"

    def _legacy_final_simulation_title(self, target_difficulty: str) -> str:
        normalized = self._normalize_difficulty(target_difficulty)
        return f"[FINAL] РС‚РѕРіРѕРІР°СЏ СЂРѕР»РµРІР°СЏ РёРіСЂР° ({normalized})"

    def _final_test_description(self, target_difficulty: str) -> str:
        normalized = self._normalize_difficulty(target_difficulty)
        if normalized == "advanced":
            return "Р¤РёРЅР°Р»СЊРЅР°СЏ РїСЂРѕРІРµСЂРєР° СѓСЂРѕРІРЅСЏ advanced: СЃР»РѕР¶РЅС‹Рµ СѓРїСЂР°РІР»РµРЅС‡РµСЃРєРёРµ СЂРµС€РµРЅРёСЏ, РєРѕРЅС„Р»РёРєС‚ РёРЅС‚РµСЂРµСЃРѕРІ Рё Р»РёРґРµСЂСЃС‚РІРѕ РІ СѓСЃР»РѕРІРёСЏС… РґР°РІР»РµРЅРёСЏ."
        if normalized == "intermediate":
            return "Р¤РёРЅР°Р»СЊРЅР°СЏ РїСЂРѕРІРµСЂРєР° СѓСЂРѕРІРЅСЏ intermediate: РєРѕРѕСЂРґРёРЅР°С†РёСЏ РєРѕРјР°РЅРґС‹, РїСЂРёРѕСЂРёС‚РёР·Р°С†РёСЏ Рё РєРѕРјРјСѓРЅРёРєР°С†РёСЏ СЃ РЅРµСЃРєРѕР»СЊРєРёРјРё СЃС‚РѕСЂРѕРЅР°РјРё."
        return "Р¤РёРЅР°Р»СЊРЅР°СЏ РїСЂРѕРІРµСЂРєР° СѓСЂРѕРІРЅСЏ beginner: Р±Р°Р·РѕРІР°СЏ РєРѕРјРјСѓРЅРёРєР°С†РёСЏ, СЌРјРїР°С‚РёСЏ Рё РїР»Р°РЅРёСЂРѕРІР°РЅРёРµ РІ СЂР°Р±РѕС‡РёС… СЃРёС‚СѓР°С†РёСЏС…."

    def _final_test_questions(self, target_difficulty: str) -> List[Dict[str, Any]]:
        normalized = self._normalize_difficulty(target_difficulty)
        if normalized == "advanced":
            return [
                {
                    "text": "РќР° РїСЂРѕРµРєС‚Рµ РѕРґРЅРѕРІСЂРµРјРµРЅРЅРѕ: РєРѕРЅС„Р»РёРєС‚ РІ РєРѕРјР°РЅРґРµ, СЂРёСЃРє СЃСЂС‹РІР° РґРµРґР»Р°Р№РЅР° Рё Р·Р°РїСЂРѕСЃ РєР»РёРµРЅС‚Р° РЅР° СЂР°СЃС€РёСЂРµРЅРёРµ РѕР±СЉС‘РјР°. РљР°РєРѕР№ РїРµСЂРІС‹Р№ СѓРїСЂР°РІР»РµРЅС‡РµСЃРєРёР№ С€Р°Рі РЅР°РёР±РѕР»РµРµ СЃРёР»СЊРЅС‹Р№?",
                    "type": "multiple_choice",
                    "options": [
                        {"text": "Р—Р°С„РёРєСЃРёСЂРѕРІР°С‚СЊ СЂРёСЃРєРё, РїСЂРѕРІРµСЃС‚Рё РєРѕСЂРѕС‚РєСѓСЋ Р°РЅС‚РёРєСЂРёР·РёСЃРЅСѓСЋ РІСЃС‚СЂРµС‡Сѓ Рё СЃРѕРіР»Р°СЃРѕРІР°С‚СЊ РїР»Р°РЅ СЃ РѕС‚РІРµС‚СЃС‚РІРµРЅРЅС‹РјРё"},
                        {"text": "РЎСЂР°Р·Сѓ РїРѕРѕР±РµС‰Р°С‚СЊ РєР»РёРµРЅС‚Сѓ РІСЃС‘ РІС‹РїРѕР»РЅРёС‚СЊ Р±РµР· РїРµСЂРµСЃРјРѕС‚СЂР° СЃСЂРѕРєРѕРІ"},
                        {"text": "РџРµСЂРµРґР°С‚СЊ РїСЂРѕР±Р»РµРјСѓ СЂСѓРєРѕРІРѕРґСЃС‚РІСѓ Рё Р¶РґР°С‚СЊ СЂРµС€РµРЅРёСЏ"},
                    ],
                },
                {
                    "text": "РљРѕРјР°РЅРґР° СЌРјРѕС†РёРѕРЅР°Р»СЊРЅРѕ РІС‹РіРѕСЂРµР»Р°, Р° Р±РёР·РЅРµСЃ РґР°РІРёС‚ РЅР° СЃРєРѕСЂРѕСЃС‚СЊ. Р§С‚Рѕ Р»СѓС‡С€Рµ РѕС‚СЂР°Р¶Р°РµС‚ Р·СЂРµР»РѕРµ Р»РёРґРµСЂСЃС‚РІРѕ?",
                    "type": "multiple_choice",
                    "options": [
                        {"text": "РЎР±Р°Р»Р°РЅСЃРёСЂРѕРІР°С‚СЊ РЅР°РіСЂСѓР·РєСѓ, РїСЂРѕСЏСЃРЅРёС‚СЊ РїСЂРёРѕСЂРёС‚РµС‚С‹ Рё РѕР±РµСЃРїРµС‡РёС‚СЊ РєРѕСЂРѕС‚РєРёРµ С†РёРєР»С‹ РѕР±СЂР°С‚РЅРѕР№ СЃРІСЏР·Рё"},
                        {"text": "РџРѕРІС‹СЃРёС‚СЊ РєРѕРЅС‚СЂРѕР»СЊ Рё РѕС‚РјРµРЅРёС‚СЊ РѕР±СЃСѓР¶РґРµРЅРёСЏ, С‡С‚РѕР±С‹ РЅРµ С‚СЂР°С‚РёС‚СЊ РІСЂРµРјСЏ"},
                        {"text": "РЎРєРѕРЅС†РµРЅС‚СЂРёСЂРѕРІР°С‚СЊСЃСЏ С‚РѕР»СЊРєРѕ РЅР° KPI, РёРіРЅРѕСЂРёСЂСѓСЏ СЌРјРѕС†РёРѕРЅР°Р»СЊРЅРѕРµ СЃРѕСЃС‚РѕСЏРЅРёРµ"},
                    ],
                },
                {
                    "text": "Р”РІР° СЃС‚РµР№РєС…РѕР»РґРµСЂР° С‚СЂРµР±СѓСЋС‚ РІР·Р°РёРјРѕРёСЃРєР»СЋС‡Р°СЋС‰РёРµ СЂРµС€РµРЅРёСЏ. РљР°Рє РґРµР№СЃС‚РІРѕРІР°С‚СЊ?",
                    "type": "multiple_choice",
                    "options": [
                        {"text": "РЎРѕР±СЂР°С‚СЊ РєСЂРёС‚РµСЂРёРё СѓСЃРїРµС…Р°, РѕС†РµРЅРёС‚СЊ РєРѕРјРїСЂРѕРјРёСЃСЃС‹ Рё РїСЂРµРґР»РѕР¶РёС‚СЊ РїСЂРѕР·СЂР°С‡РЅС‹Р№ РІР°СЂРёР°РЅС‚ СЃ РїРѕСЃР»РµРґСЃС‚РІРёСЏРјРё"},
                        {"text": "РџРѕРґРґРµСЂР¶Р°С‚СЊ С‚РѕРіРѕ, РєС‚Рѕ Р·Р°РЅРёРјР°РµС‚ Р±РѕР»РµРµ РІС‹СЃРѕРєСѓСЋ РґРѕР»Р¶РЅРѕСЃС‚СЊ"},
                        {"text": "РћС‚Р»РѕР¶РёС‚СЊ СЂРµС€РµРЅРёРµ РґРѕ РїРѕСЃР»РµРґРЅРµРіРѕ РґРЅСЏ"},
                    ],
                },
                {
                    "text": "РљР°РєРѕР№ РїРѕРґС…РѕРґ Р»СѓС‡С€Рµ РІСЃРµРіРѕ РїРѕРєР°Р·С‹РІР°РµС‚ РєСЂРёС‚РёС‡РµСЃРєРѕРµ РјС‹С€Р»РµРЅРёРµ РІ СѓРїСЂР°РІР»РµРЅС‡РµСЃРєРѕР№ Р·Р°РґР°С‡Рµ?",
                    "type": "multiple_choice",
                    "options": [
                        {"text": "РџСЂРѕРІРµСЂРёС‚СЊ РёСЃС…РѕРґРЅС‹Рµ РґРѕРїСѓС‰РµРЅРёСЏ, РґР°РЅРЅС‹Рµ Рё Р°Р»СЊС‚РµСЂРЅР°С‚РёРІС‹ РїРµСЂРµРґ СЂРµС€РµРЅРёРµРј"},
                        {"text": "РћРїРёСЂР°СЏСЃСЊ РЅР° РѕРїС‹С‚, СЃСЂР°Р·Сѓ РІС‹Р±СЂР°С‚СЊ Р·РЅР°РєРѕРјС‹Р№ РІР°СЂРёР°РЅС‚"},
                        {"text": "РЎРґРµР»Р°С‚СЊ РІС‹Р±РѕСЂ РїРѕ РЅР°СЃС‚СЂРѕРµРЅРёСЋ РєРѕРјР°РЅРґС‹"},
                    ],
                },
            ]
        if normalized == "intermediate":
            return [
                {
                    "text": "РќР° РµР¶РµРЅРµРґРµР»СЊРЅРѕР№ РІСЃС‚СЂРµС‡Рµ РІРѕР·РЅРёРє СЃРїРѕСЂ РјРµР¶РґСѓ РґРІСѓРјСЏ РєРѕР»Р»РµРіР°РјРё, СЃСЂРѕРєРё РїРѕРґ СѓРіСЂРѕР·РѕР№. Р’Р°С€ РїРµСЂРІС‹Р№ С€Р°Рі?",
                    "type": "multiple_choice",
                    "options": [
                        {"text": "РћСЃС‚Р°РЅРѕРІРёС‚СЊ СЃРїРѕСЂ, СѓС‚РѕС‡РЅРёС‚СЊ С„Р°РєС‚С‹ Рё РґРѕРіРѕРІРѕСЂРёС‚СЊСЃСЏ Рѕ СЃР»РµРґСѓСЋС‰РёС… РґРµР№СЃС‚РІРёСЏС… РїРѕ СЃСЂРѕРєР°Рј"},
                        {"text": "Р’С‹Р±СЂР°С‚СЊ РѕРґРЅСѓ СЃС‚РѕСЂРѕРЅСѓ Р±РµР· РѕР±СЃСѓР¶РґРµРЅРёСЏ"},
                        {"text": "РџРµСЂРµРЅРµСЃС‚Рё СЂРµС€РµРЅРёРµ РЅР° СЃР»РµРґСѓСЋС‰СѓСЋ РЅРµРґРµР»СЋ"},
                    ],
                },
                {
                    "text": "РљР»РёРµРЅС‚ РїСЂРѕСЃРёС‚ СЃСЂРѕС‡РЅСѓСЋ РґРѕСЂР°Р±РѕС‚РєСѓ, РєРѕРјР°РЅРґР° СѓР¶Рµ РїРµСЂРµРіСЂСѓР¶РµРЅР°. РљР°Рє РєРѕСЂСЂРµРєС‚РЅРѕ РѕС‚РІРµС‚РёС‚СЊ?",
                    "type": "multiple_choice",
                    "options": [
                        {"text": "РЈС‚РѕС‡РЅРёС‚СЊ РїСЂРёРѕСЂРёС‚РµС‚, РїРѕРєР°Р·Р°С‚СЊ РІР»РёСЏРЅРёРµ РЅР° С‚РµРєСѓС‰РёР№ РїР»Р°РЅ Рё РїСЂРµРґР»РѕР¶РёС‚СЊ РІР°СЂРёР°РЅС‚С‹"},
                        {"text": "РЎСЂР°Р·Сѓ СЃРѕРіР»Р°СЃРёС‚СЊСЃСЏ Р±РµР· РїРµСЂРµСЃРјРѕС‚СЂР° РїР»Р°РЅР°"},
                        {"text": "РћС‚РєР°Р·Р°С‚СЊ Р±РµР· РѕР±СЉСЏСЃРЅРµРЅРёР№"},
                    ],
                },
                {
                    "text": "Р’С‹ РІРµРґС‘С‚Рµ РґРІРµ РїР°СЂР°Р»Р»РµР»СЊРЅС‹Рµ Р·Р°РґР°С‡Рё СЃ Р±Р»РёР·РєРёРјРё РґРµРґР»Р°Р№РЅР°РјРё. Р§С‚Рѕ СЌС„С„РµРєС‚РёРІРЅРµРµ?",
                    "type": "multiple_choice",
                    "options": [
                        {"text": "Р Р°Р·Р±РёС‚СЊ Р·Р°РґР°С‡Рё РЅР° СЌС‚Р°РїС‹, РЅР°Р·РЅР°С‡РёС‚СЊ РїСЂРёРѕСЂРёС‚РµС‚С‹ Рё РєРѕРЅС‚СЂРѕР»СЊРЅС‹Рµ С‚РѕС‡РєРё"},
                        {"text": "Р Р°Р±РѕС‚Р°С‚СЊ С‚РѕР»СЊРєРѕ РЅР°Рґ Р±РѕР»РµРµ РёРЅС‚РµСЂРµСЃРЅРѕР№ Р·Р°РґР°С‡РµР№"},
                        {"text": "Р–РґР°С‚СЊ, РїРѕРєР° РєС‚Рѕ-С‚Рѕ РѕРїСЂРµРґРµР»РёС‚ РїСЂРёРѕСЂРёС‚РµС‚ Р·Р° РІР°СЃ"},
                    ],
                },
                {
                    "text": "РЎРѕС‚СЂСѓРґРЅРёРє РІ РЅР°РїСЂСЏР¶РµРЅРёРё Рё РѕС‚РІРµС‡Р°РµС‚ СЂРµР·РєРѕ. РљР°Рє Р»СѓС‡С€Рµ РѕС‚СЂРµР°РіРёСЂРѕРІР°С‚СЊ?",
                    "type": "multiple_choice",
                    "options": [
                        {"text": "РЎРѕС…СЂР°РЅСЏС‚СЊ СЃРїРѕРєРѕР№СЃС‚РІРёРµ, РїСЂРёР·РЅР°С‚СЊ СЌРјРѕС†РёРё Рё РІРµСЂРЅСѓС‚СЊ СЂР°Р·РіРѕРІРѕСЂ Рє С„Р°РєС‚Р°Рј"},
                        {"text": "РћС‚РІРµС‚РёС‚СЊ РІ С‚РѕРј Р¶Рµ С‚РѕРЅРµ"},
                        {"text": "РџСЂРµСЂРІР°С‚СЊ РѕР±С‰РµРЅРёРµ РґРѕ РєРѕРЅС†Р° РґРЅСЏ"},
                    ],
                },
            ]
        return [
            {
                "text": "РљРѕР»Р»РµРіР° РЅРµ РїРѕРЅСЏР» Р·Р°РґР°С‡Сѓ Рё Р·Р°РјРµС‚РЅРѕ СЂР°Р·РґСЂР°Р¶С‘РЅ. Р’Р°С€ СЃР°РјС‹Р№ РїРѕР»РµР·РЅС‹Р№ РїРµСЂРІС‹Р№ С€Р°Рі?",
                "type": "multiple_choice",
                "options": [
                    {"text": "РЎРїРѕРєРѕР№РЅРѕ СѓС‚РѕС‡РЅРёС‚СЊ С†РµР»СЊ Рё РїРµСЂРµС„РѕСЂРјСѓР»РёСЂРѕРІР°С‚СЊ Р·Р°РґР°С‡Сѓ РїСЂРѕСЃС‚С‹РјРё С€Р°РіР°РјРё"},
                    {"text": "РЎСЂР°Р·Сѓ РїРµСЂРµРґР°С‚СЊ Р·Р°РґР°С‡Сѓ РґСЂСѓРіРѕРјСѓ С‡РµР»РѕРІРµРєСѓ"},
                    {"text": "РРіРЅРѕСЂРёСЂРѕРІР°С‚СЊ СЌРјРѕС†РёРё Рё С‚СЂРµР±РѕРІР°С‚СЊ Р±С‹СЃС‚СЂС‹Р№ СЂРµР·СѓР»СЊС‚Р°С‚"},
                ],
            },
            {
                "text": "РљР°Рє Р»СѓС‡С€Рµ СЂР°СЃРїСЂРµРґРµР»РёС‚СЊ СЂР°Р±РѕС‡РёРµ Р·Р°РґР°С‡Рё РЅР° РґРµРЅСЊ?",
                "type": "multiple_choice",
                "options": [
                    {"text": "РћРїСЂРµРґРµР»РёС‚СЊ РїСЂРёРѕСЂРёС‚РµС‚С‹ Рё РѕС†РµРЅРёС‚СЊ РІСЂРµРјСЏ РЅР° РєР°Р¶РґСѓСЋ Р·Р°РґР°С‡Сѓ"},
                    {"text": "РќР°С‡РёРЅР°С‚СЊ С‚РѕР»СЊРєРѕ СЃ СЃР°РјС‹С… Р»С‘РіРєРёС… Р·Р°РґР°С‡"},
                    {"text": "Р”РµР»Р°С‚СЊ Р·Р°РґР°С‡Рё РІ СЃР»СѓС‡Р°Р№РЅРѕРј РїРѕСЂСЏРґРєРµ"},
                ],
            },
            {
                "text": "РљР»РёРµРЅС‚ РїСЂРѕСЃРёС‚ РІРЅРµСЃС‚Рё РёР·РјРµРЅРµРЅРёСЏ РІ РїРѕСЃР»РµРґРЅРёР№ РјРѕРјРµРЅС‚. РљР°Рє РґРµР№СЃС‚РІРѕРІР°С‚СЊ?",
                "type": "multiple_choice",
                "options": [
                    {"text": "РЈС‚РѕС‡РЅРёС‚СЊ С‚СЂРµР±РѕРІР°РЅРёСЏ, РІР»РёСЏРЅРёРµ РЅР° СЃСЂРѕРєРё Рё СЃРѕРіР»Р°СЃРѕРІР°С‚СЊ СЂРµР°Р»РёСЃС‚РёС‡РЅС‹Р№ РІР°СЂРёР°РЅС‚"},
                    {"text": "РЎСЂР°Р·Сѓ СЃРѕРіР»Р°СЃРёС‚СЊСЃСЏ Р±РµР· СѓС‚РѕС‡РЅРµРЅРёР№"},
                    {"text": "РЎСЂР°Р·Сѓ РѕС‚РєР°Р·Р°С‚СЊСЃСЏ Р±РµР· РѕР±СЃСѓР¶РґРµРЅРёСЏ"},
                ],
            },
            {
                "text": "Р’ РєРѕРјР°РЅРґРµ РІРѕР·РЅРёРєР»Рѕ РЅР°РїСЂСЏР¶РµРЅРёРµ. Р§С‚Рѕ РїРѕРјРѕРіР°РµС‚ СЃРЅРёР·РёС‚СЊ РєРѕРЅС„Р»РёРєС‚?",
                "type": "multiple_choice",
                "options": [
                    {"text": "Р’С‹СЃР»СѓС€Р°С‚СЊ РѕР±Рµ СЃС‚РѕСЂРѕРЅС‹ Рё Р·Р°С„РёРєСЃРёСЂРѕРІР°С‚СЊ РґРѕРіРѕРІРѕСЂС‘РЅРЅРѕСЃС‚Рё"},
                    {"text": "РќР°Р·РЅР°С‡РёС‚СЊ РІРёРЅРѕРІРЅРѕРіРѕ Р±РµР· СЂР°Р·Р±РѕСЂР° СЃРёС‚СѓР°С†РёРё"},
                    {"text": "РЎРґРµР»Р°С‚СЊ РІРёРґ, С‡С‚Рѕ РїСЂРѕР±Р»РµРјС‹ РЅРµС‚"},
                ],
            },
        ]

    def _final_simulation_description(self, target_difficulty: str) -> str:
        normalized = self._normalize_difficulty(target_difficulty)
        if normalized == "advanced":
            return "Р¤РёРЅР°Р»СЊРЅР°СЏ СЂРѕР»РµРІР°СЏ РёРіСЂР° СѓСЂРѕРІРЅСЏ advanced: СЃС‚СЂРµСЃСЃРѕРІР°СЏ СЃРёС‚СѓР°С†РёСЏ СЃ РєРѕРЅС„Р»РёРєС‚РѕРј РёРЅС‚РµСЂРµСЃРѕРІ, Р»РёРґРµСЂСЃС‚РІРѕРј Рё РїСЂРёРЅСЏС‚РёРµРј СЂРµС€РµРЅРёР№ РІ СѓСЃР»РѕРІРёСЏС… РІС‹СЃРѕРєРѕР№ РЅРµРѕРїСЂРµРґРµР»С‘РЅРЅРѕСЃС‚Рё."
        if normalized == "intermediate":
            return "Р¤РёРЅР°Р»СЊРЅР°СЏ СЂРѕР»РµРІР°СЏ РёРіСЂР° СѓСЂРѕРІРЅСЏ intermediate: СѓРїСЂР°РІР»РµРЅРёРµ РєРѕРјРјСѓРЅРёРєР°С†РёРµР№ РјРµР¶РґСѓ РєРѕРјР°РЅРґРѕР№ Рё Р·Р°РєР°Р·С‡РёРєРѕРј РїСЂРё СЂРёСЃРєРµ СЃСЂС‹РІР° СЃСЂРѕРєРѕРІ."
        return "Р¤РёРЅР°Р»СЊРЅР°СЏ СЂРѕР»РµРІР°СЏ РёРіСЂР° СѓСЂРѕРІРЅСЏ beginner: РїСЂРѕРІРµСЂРєР° Р±Р°Р·РѕРІРѕР№ РєРѕРјРјСѓРЅРёРєР°С†РёРё, СЌРјРїР°С‚РёРё Рё С‚Р°Р№Рј-РјРµРЅРµРґР¶РјРµРЅС‚Р° РІ СЂР°Р±РѕС‡РµРј РґРёР°Р»РѕРіРµ."

    def _final_simulation_intro(self, target_difficulty: str) -> str:
        normalized = self._normalize_difficulty(target_difficulty)
        if normalized == "advanced":
            return (
                "РЎРёС‚СѓР°С†РёСЏ: РІС‹ СЂСѓРєРѕРІРѕРґРёС‚Рµ РєСЂРѕСЃСЃ-С„СѓРЅРєС†РёРѕРЅР°Р»СЊРЅС‹Рј РїСЂРѕРµРєС‚РѕРј, РєРѕС‚РѕСЂС‹Р№ РґРѕР»Р¶РµРЅ РІС‹Р№С‚Рё РІ СЂРµР»РёР· С‡РµСЂРµР· 48 С‡Р°СЃРѕРІ. "
                "РўРµС…РЅРёС‡РµСЃРєРёР№ Р»РёРґРµСЂ СЃРѕРѕР±С‰Р°РµС‚ Рѕ РєСЂРёС‚РёС‡РµСЃРєРѕРј СЂРёСЃРєРµ РІ Р±РµР·РѕРїР°СЃРЅРѕСЃС‚Рё, РєРѕРјРјРµСЂС‡РµСЃРєРёР№ РґРёСЂРµРєС‚РѕСЂ С‚СЂРµР±СѓРµС‚ РЅРµ РїРµСЂРµРЅРѕСЃРёС‚СЊ РґР°С‚Сѓ Р·Р°РїСѓСЃРєР°, "
                "Р° РєР»СЋС‡РµРІРѕР№ РєР»РёРµРЅС‚ РѕРґРЅРѕРІСЂРµРјРµРЅРЅРѕ РїСЂРѕСЃРёС‚ РґРѕР±Р°РІРёС‚СЊ РЅРѕРІС‹Р№ С„СѓРЅРєС†РёРѕРЅР°Р» РІ СЂРµР»РёР·. "
                "Р’РЅСѓС‚СЂРё РєРѕРјР°РЅРґС‹ РЅР°С‡Р°Р»РѕСЃСЊ РЅР°РїСЂСЏР¶РµРЅРёРµ: С‡Р°СЃС‚СЊ СЃРѕС‚СЂСѓРґРЅРёРєРѕРІ РЅР°СЃС‚Р°РёРІР°РµС‚ РЅР° РЅРµРјРµРґР»РµРЅРЅРѕРј Р·Р°РјРѕСЂР°Р¶РёРІР°РЅРёРё РёР·РјРµРЅРµРЅРёР№, "
                "С‡Р°СЃС‚СЊ Р±РѕРёС‚СЃСЏ РїРѕС‚РµСЂСЏС‚СЊ РєР»РёРµРЅС‚Р° РёР·-Р·Р° РѕС‚РєР°Р·Р°. "
                "Р’Р°С€Р° Р·Р°РґР°С‡Р° РІ РґРёР°Р»РѕРіРµ: СѓРґРµСЂР¶Р°С‚СЊ РєРѕРЅСЃС‚СЂСѓРєС‚РёРІРЅСѓСЋ РєРѕРјРјСѓРЅРёРєР°С†РёСЋ, РїСЂРѕСЏРІРёС‚СЊ СЌРјРѕС†РёРѕРЅР°Р»СЊРЅСѓСЋ СѓСЃС‚РѕР№С‡РёРІРѕСЃС‚СЊ Рё СЌРјРїР°С‚РёСЋ, "
                "СЃРѕР±СЂР°С‚СЊ С„Р°РєС‚С‹, РѕС†РµРЅРёС‚СЊ СЂРёСЃРєРё Рё РїСЂРµРґР»РѕР¶РёС‚СЊ Р»РёРґРµСЂСЃРєРёР№ РїР»Р°РЅ РґРµР№СЃС‚РІРёР№ СЃ РїРѕРЅСЏС‚РЅС‹РјРё СЃСЂРѕРєР°РјРё, РѕС‚РІРµС‚СЃС‚РІРµРЅРЅС‹РјРё Рё РєСЂРёС‚РµСЂРёСЏРјРё РїСЂРёРЅСЏС‚РёСЏ СЂРµС€РµРЅРёСЏ."
            )
        if normalized == "intermediate":
            return (
                "РЎРёС‚СѓР°С†РёСЏ: РІС‹ РєРѕРѕСЂРґРёРЅРёСЂСѓРµС‚Рµ СЂР°Р±РѕС‡СѓСЋ РіСЂСѓРїРїСѓ, Рё Р·Р° РґРІР° РґРЅСЏ РґРѕ РґРµРґР»Р°Р№РЅР° РІС‹СЏСЃРЅСЏРµС‚СЃСЏ, С‡С‚Рѕ РѕРґРЅР° РёР· РєР»СЋС‡РµРІС‹С… Р·Р°РґР°С‡ РѕС‚СЃС‚Р°С‘С‚. "
                "РћРґРёРЅ СЃРѕС‚СЂСѓРґРЅРёРє СЂР°Р·РґСЂР°Р¶С‘РЅ Рё СЃС‡РёС‚Р°РµС‚, С‡С‚Рѕ РµРјСѓ РґР°Р»Рё СЃР»РёС€РєРѕРј Р±РѕР»СЊС€РѕР№ РѕР±СЉС‘Рј, РІС‚РѕСЂРѕР№ РјРѕР»С‡РёС‚ Рѕ СЂРёСЃРєР°С…, "
                "Р° Р·Р°РєР°Р·С‡РёРє РїСЂРѕСЃРёС‚ РїРѕРґС‚РІРµСЂРґРёС‚СЊ С„РёРЅР°Р»СЊРЅС‹Р№ СЃСЂРѕРє Р±РµР· РїРµСЂРµРЅРѕСЃР°. "
                "Р’Р°С€Р° Р·Р°РґР°С‡Р° РІ РґРёР°Р»РѕРіРµ: СЃРїРѕРєРѕР№РЅРѕ РІС‹СЃС‚СЂРѕРёС‚СЊ РѕР±С‰РµРЅРёРµ, СѓС‚РѕС‡РЅРёС‚СЊ РїСЂРёС‡РёРЅС‹ Р·Р°РґРµСЂР¶РєРё, СЂР°СЃСЃС‚Р°РІРёС‚СЊ РїСЂРёРѕСЂРёС‚РµС‚С‹, "
                "СЃРѕРіР»Р°СЃРѕРІР°С‚СЊ СЂРµР°Р»РёСЃС‚РёС‡РЅС‹Р№ РїР»Р°РЅ Рё РґРѕРіРѕРІРѕСЂРёС‚СЊСЃСЏ СЃ СѓС‡Р°СЃС‚РЅРёРєР°РјРё Рѕ РєРѕРЅРєСЂРµС‚РЅС‹С… С€Р°РіР°С… Рё РѕС‚РІРµС‚СЃС‚РІРµРЅРЅРѕСЃС‚Рё."
            )
        return (
            "РЎРёС‚СѓР°С†РёСЏ: РІС‹ РѕС‚РІРµС‡Р°РµС‚Рµ Р·Р° РЅРµР±РѕР»СЊС€РѕР№ СЂР°Р±РѕС‡РёР№ Р±Р»РѕРє РІ РєРѕРјР°РЅРґРµ. "
            "РџРµСЂРµРґ РґРµРґР»Р°Р№РЅРѕРј РІС‹СЏСЃРЅРёР»РѕСЃСЊ, С‡С‚Рѕ РєРѕР»Р»РµРіР° РЅРµ РґРѕ РєРѕРЅС†Р° РїРѕРЅСЏР» Р·Р°РґР°С‡Сѓ Рё РЅРµСЂРІРЅРёС‡Р°РµС‚, "
            "Р° РєР»РёРµРЅС‚ РѕР¶РёРґР°РµС‚ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ СЂРµР·СѓР»СЊС‚Р°С‚Р° РІ СЃСЂРѕРє. "
            "Р’Р°С€Р° Р·Р°РґР°С‡Р° РІ РґРёР°Р»РѕРіРµ: РїРѕРґРґРµСЂР¶Р°С‚СЊ РєРѕРЅСЃС‚СЂСѓРєС‚РёРІРЅС‹Р№ С‚РѕРЅ, РїСЂРѕСЏРІРёС‚СЊ СЌРјРїР°С‚РёСЋ, "
            "РїСЂРѕСЃС‚С‹РјРё СЃР»РѕРІР°РјРё СѓС‚РѕС‡РЅРёС‚СЊ РїСЂРёРѕСЂРёС‚РµС‚С‹ Рё РґРѕРіРѕРІРѕСЂРёС‚СЊСЃСЏ Рѕ РїРѕРЅСЏС‚РЅРѕРј РїР»Р°РЅРµ РґРµР№СЃС‚РІРёР№, С‡С‚РѕР±С‹ РєРѕРјР°РЅРґР° СѓСЃРїРµР»Р° РІРѕРІСЂРµРјСЏ."
        )

    def _normalize_question_payload(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        text = str(payload.get("text") or "").strip()
        if not text:
            return None

        question_type = str(payload.get("type") or "text").strip().lower() or "text"
        options_raw = payload.get("options")
        options: Optional[List[Dict[str, Any]]] = None
        if isinstance(options_raw, list):
            normalized_options: List[Dict[str, Any]] = []
            for option in options_raw:
                if isinstance(option, dict):
                    option_text = str(
                        option.get("text")
                        or option.get("label")
                        or option.get("value")
                        or ""
                    ).strip()
                else:
                    option_text = str(option or "").strip()
                if option_text:
                    normalized_options.append({"text": option_text})
            if normalized_options:
                options = normalized_options

        return {
            "text": text,
            "type": question_type,
            "options": options,
        }

    async def _sync_test_questions(
        self,
        test_id: int,
        expected_questions: List[Dict[str, Any]],
        db: AsyncSession,
    ) -> None:
        normalized_expected: List[Dict[str, Any]] = []
        for item in expected_questions:
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_question_payload(item)
            if normalized is not None:
                normalized_expected.append(normalized)

        if not normalized_expected:
            return

        existing_res = await db.execute(
            select(Question).where(Question.test_id == int(test_id)).order_by(Question.id.asc())
        )
        existing_questions = list(existing_res.scalars().all())
        normalized_existing: List[Dict[str, Any]] = []
        for question in existing_questions:
            normalized = self._normalize_question_payload(
                {
                    "text": question.text,
                    "type": question.type,
                    "options": question.options,
                }
            )
            if normalized is not None:
                normalized_existing.append(normalized)

        if normalized_existing == normalized_expected:
            return

        for question in existing_questions:
            await db.delete(question)
        await db.flush()

        for question in normalized_expected:
            db.add(
                Question(
                    test_id=int(test_id),
                    text=question["text"],
                    type=question["type"],
                    options=question["options"],
                    correct_answer=None,
                )
            )
        await db.flush()

    def _is_final_title(self, value: str) -> bool:
        normalized = self._normalize_text(value)
        if not normalized:
            return False
        return (
            "[final]" in normalized
            or normalized.startswith("РёС‚РѕРіРѕРІС‹Р№ С‚РµСЃС‚ (")
            or normalized.startswith("РёС‚РѕРіРѕРІР°СЏ СЂРѕР»РµРІР°СЏ РёРіСЂР° (")
            or normalized.startswith("final test (")
            or normalized.startswith("final simulation (")
            or "С„РёРЅР°Р»СЊРЅР°СЏ РїСЂРѕРІРµСЂРєР° СѓСЂРѕРІРЅСЏ" in normalized
            or "С„РёРЅР°Р»СЊРЅР°СЏ СЂРѕР»РµРІР°СЏ РёРіСЂР° СѓСЂРѕРІРЅСЏ" in normalized
        )

    def _is_final_test(self, test: Test) -> bool:
        title = str(getattr(test, "title", "") or "")
        description = str(getattr(test, "description", "") or "")
        return self._is_final_title(title) or self._is_final_title(description)

    def _parse_iso_datetime(self, value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            parsed = datetime.fromisoformat(str(value))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return None

    def _material_progress_percentage(self, article_opened: bool, test_completed: bool) -> float:
        score = 0
        if article_opened:
            score += 50
        if test_completed:
            score += 50
        return float(score)

    def _compute_components_progress(
        self,
        tasks: List[Dict[str, Any]],
        materials: List[Dict[str, Any]],
        material_progress: Dict[str, Dict[str, Any]],
    ) -> Dict[str, float]:
        completed_tasks = sum(1 for task in tasks if str(task.get("status")).lower() == "completed")
        opened_articles = 0
        completed_material_tests = 0
        for material in materials:
            material_id = str(material.get("id", ""))
            progress = material_progress.get(material_id, {})
            if bool(progress.get("article_opened")):
                opened_articles += 1
            if bool(progress.get("test_completed")):
                completed_material_tests += 1

        completed = completed_tasks + opened_articles + completed_material_tests
        total = len(tasks) + len(materials) * 2
        percentage = (completed / total * 100.0) if total > 0 else 0.0
        return {
            "completed": completed,
            "total": total,
            "percentage": round(percentage, 2),
        }

    def _difficulty_ru_label(self, difficulty: str) -> str:
        normalized = str(difficulty or "").strip().lower()
        if normalized == "advanced":
            return "Р С—РЎР‚Р С•Р Т‘Р Р†Р С‘Р Р…РЎС“РЎвЂљРЎвЂ№Р в„–"
        if normalized == "intermediate":
            return "РЎРѓРЎР‚Р ВµР Т‘Р Р…Р С‘Р в„–"
        return "Р Р…Р В°РЎвЂЎР В°Р В»РЎРЉР Р…РЎвЂ№Р в„–"

    def _build_block_achievement_title(self, content: Dict[str, Any]) -> str:
        target = str(content.get("target_difficulty") or "beginner")
        return f"Р СџРЎР‚Р С•Р в„–Р Т‘Р ВµР Р… Р С—Р ВµРЎР‚Р Р†РЎвЂ№Р в„– {self._difficulty_ru_label(target)} Р В±Р В»Р С•Р С”"

    def _collect_block_achievements(self, plans: List[DevelopmentPlan]) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        seen_fallback: set[tuple[str, str]] = set()

        for plan in plans:
            content = plan.content if isinstance(plan.content, dict) else {}

            raw_achievements = content.get("block_achievements")
            plan_achievements = list(raw_achievements) if isinstance(raw_achievements, list) else []

            # Backward compatibility: recover achievement from final_stage if list is absent.
            final_stage = content.get("final_stage")
            if isinstance(final_stage, dict) and bool(final_stage.get("level_up_applied")):
                title = str(final_stage.get("achievement_title") or "").strip()
                if title:
                    fallback_id = f"block_{plan.id}_{str(content.get('target_difficulty') or 'unknown')}"
                    plan_achievements.append(
                        {
                            "id": fallback_id,
                            "title": title,
                            "achieved_at": final_stage.get("completed_at"),
                        }
                    )

            for item in plan_achievements:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                if not title:
                    continue

                item_id = str(item.get("id") or "").strip()
                achieved_at = item.get("achieved_at")
                achieved_at_key = str(achieved_at or "")

                if item_id:
                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)
                else:
                    fallback_key = (title, achieved_at_key)
                    if fallback_key in seen_fallback:
                        continue
                    seen_fallback.add(fallback_key)

                merged.append(
                    {
                        "id": item_id or f"legacy_{plan.id}_{len(merged) + 1}",
                        "title": title,
                        "achieved_at": achieved_at,
                    }
                )

        def _sort_key(item: Dict[str, Any]) -> float:
            parsed = self._parse_iso_datetime(item.get("achieved_at"))
            if parsed is None:
                return 0.0
            return float(parsed.timestamp())

        merged.sort(key=_sort_key, reverse=True)
        return merged

    def _assign_tests_to_materials(
        self,
        materials: List[Dict[str, Any]],
        tests: List[Test],
        existing_map: Dict[str, Any],
        completed_test_ids: Optional[set[int]] = None,
    ) -> Dict[str, int]:
        completed_ids = {
            int(test_id)
            for test_id in (completed_test_ids or set())
            if str(test_id).isdigit() and int(test_id) > 0
        }
        filtered_tests = [t for t in tests if str(t.type).lower() != "simulation" and not self._is_final_test(t)]
        tests_by_id = {int(t.id): t for t in filtered_tests}
        skill_keywords = self._skill_keywords()

        tests_by_skill: Dict[str, List[int]] = {skill: [] for skill in skill_keywords.keys()}
        fallback_ids: List[int] = []
        for test in filtered_tests:
            text = f"{test.title} {test.description}".lower()
            fallback_ids.append(int(test.id))
            matched_skill: Optional[str] = None
            for skill, keywords in skill_keywords.items():
                if any(keyword in text for keyword in keywords):
                    matched_skill = skill
                    break
            if matched_skill:
                tests_by_skill[matched_skill].append(int(test.id))

        usage_cursor: Dict[str, int] = {skill: 0 for skill in skill_keywords.keys()}
        fallback_cursor = 0
        mapping: Dict[str, int] = {}
        used_ids: set[int] = set()

        def _can_reuse_existing(
            current_id: int,
            skill_candidate_ids: List[int],
        ) -> bool:
            if current_id not in tests_by_id or current_id in used_ids:
                return False
            if current_id not in completed_ids:
                return True
            if not skill_candidate_ids:
                return True
            has_new_alternative = any(
                candidate_id != current_id and candidate_id not in completed_ids
                for candidate_id in skill_candidate_ids
            )
            return not has_new_alternative

        def _pick_candidate(candidate_ids: List[int], start_idx: int) -> tuple[Optional[int], int]:
            if not candidate_ids:
                return None, start_idx

            # Prefer tests that user has not completed in previous plan blocks.
            for offset in range(len(candidate_ids)):
                idx = (start_idx + offset) % len(candidate_ids)
                candidate_id = candidate_ids[idx]
                if candidate_id in used_ids or candidate_id in completed_ids:
                    continue
                return candidate_id, idx + 1

            # Then allow any non-used test.
            for offset in range(len(candidate_ids)):
                idx = (start_idx + offset) % len(candidate_ids)
                candidate_id = candidate_ids[idx]
                if candidate_id in used_ids:
                    continue
                return candidate_id, idx + 1

            # If all are used, still prefer not-completed to reduce repetition.
            for offset in range(len(candidate_ids)):
                idx = (start_idx + offset) % len(candidate_ids)
                candidate_id = candidate_ids[idx]
                if candidate_id in completed_ids:
                    continue
                return candidate_id, idx + 1

            idx = start_idx % len(candidate_ids)
            return candidate_ids[idx], start_idx + 1

        for material in materials:
            material_id = str(material.get("id", "")).strip()
            if not material_id:
                continue

            current_value = existing_map.get(material_id)
            try:
                current_id = int(current_value) if current_value is not None else None
            except Exception:
                current_id = None

            skill = str(material.get("skill", "")).strip().lower()
            candidate_ids = tests_by_skill.get(skill) or []

            if current_id is not None and _can_reuse_existing(current_id, candidate_ids):
                mapping[material_id] = current_id
                used_ids.add(current_id)
                continue

            selected_id: Optional[int] = None
            if candidate_ids:
                selected_id, next_cursor = _pick_candidate(candidate_ids, usage_cursor.get(skill, 0))
                usage_cursor[skill] = next_cursor

            if selected_id is None and fallback_ids:
                selected_id, fallback_cursor = _pick_candidate(fallback_ids, fallback_cursor)

            if selected_id is not None:
                mapping[material_id] = selected_id
                used_ids.add(selected_id)

        return mapping

    def _next_level_floor_for_difficulty(self, difficulty: str) -> int:
        normalized = str(difficulty or "").strip().lower()
        if normalized == "advanced":
            return 85
        if normalized == "intermediate":
            return 75
        return 45

    async def _ensure_final_stage_tests(
        self,
        content: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        target_difficulty = self._normalize_difficulty(content.get("target_difficulty"))
        content["target_difficulty"] = target_difficulty
        final_stage = content.get("final_stage")
        if not isinstance(final_stage, dict):
            final_stage = {}

        final_test_title = self._final_test_title(target_difficulty)
        legacy_final_test_title = self._legacy_final_test_title(target_difficulty)
        final_simulation_title = self._final_simulation_title(target_difficulty)
        legacy_final_simulation_title = self._legacy_final_simulation_title(target_difficulty)

        final_test = None
        final_test_id_raw = final_stage.get("final_test_id")
        try:
            final_test_id = int(final_test_id_raw) if final_test_id_raw is not None else None
        except Exception:
            final_test_id = None
        if final_test_id is not None:
            test_res = await db.execute(select(Test).where(Test.id == final_test_id))
            candidate = test_res.scalars().first()
            if candidate and str(candidate.type).lower() != "simulation":
                final_test = candidate

        if final_test is None:
            test_res = await db.execute(
                select(Test).where(
                    Test.type == "quiz",
                    Test.title.in_([final_test_title, legacy_final_test_title]),
                )
            )
            final_test = test_res.scalars().first()

        if final_test is None:
            final_test = Test(
                title=final_test_title,
                description=self._final_test_description(target_difficulty),
                type="quiz",
            )
            db.add(final_test)
            await db.flush()
        else:
            final_test.title = self._strip_final_marker(str(final_test.title or final_test_title)) or final_test_title
            final_test.description = self._final_test_description(target_difficulty)
        await self._sync_test_questions(
            test_id=int(final_test.id),
            expected_questions=self._final_test_questions(target_difficulty),
            db=db,
        )

        final_simulation = None
        final_simulation_id_raw = final_stage.get("final_simulation_id")
        try:
            final_simulation_id = int(final_simulation_id_raw) if final_simulation_id_raw is not None else None
        except Exception:
            final_simulation_id = None
        if final_simulation_id is not None:
            simulation_res = await db.execute(select(Test).where(Test.id == final_simulation_id))
            candidate = simulation_res.scalars().first()
            if candidate and str(candidate.type).lower() == "simulation":
                final_simulation = candidate

        if final_simulation is None:
            simulation_res = await db.execute(
                select(Test).where(
                    Test.type == "simulation",
                    Test.title.in_([final_simulation_title, legacy_final_simulation_title]),
                )
            )
            final_simulation = simulation_res.scalars().first()

        if final_simulation is None:
            final_simulation = Test(
                title=final_simulation_title,
                description=self._final_simulation_description(target_difficulty),
                type="simulation",
            )
            db.add(final_simulation)
            await db.flush()
        else:
            final_simulation.title = self._strip_final_marker(
                str(final_simulation.title or final_simulation_title)
            ) or final_simulation_title
            final_simulation.description = self._final_simulation_description(target_difficulty)
        await self._sync_test_questions(
            test_id=int(final_simulation.id),
            expected_questions=[
                {
                    "text": self._final_simulation_intro(target_difficulty),
                    "type": "text",
                    "options": None,
                }
            ],
            db=db,
        )

        final_stage["final_test_id"] = int(final_test.id)
        final_stage["final_simulation_id"] = int(final_simulation.id)
        return final_stage

    async def _get_completion_test_ids(
        self,
        user_id: int,
        test_ids: List[int],
        db: AsyncSession,
        completed_after: Optional[datetime] = None,
        completed_before: Optional[datetime] = None,
    ) -> set[int]:
        unique_ids = sorted({int(test_id) for test_id in test_ids if int(test_id) > 0})
        if not unique_ids:
            return set()

        completed_after_utc: Optional[datetime] = None
        if completed_after is not None:
            if completed_after.tzinfo is None:
                completed_after_utc = completed_after.replace(tzinfo=timezone.utc)
            else:
                completed_after_utc = completed_after

        completed_before_utc: Optional[datetime] = None
        if completed_before is not None:
            if completed_before.tzinfo is None:
                completed_before_utc = completed_before.replace(tzinfo=timezone.utc)
            else:
                completed_before_utc = completed_before

        completed_ids: set[int] = set()
        results_query = select(UserTestResult.test_id).where(
            UserTestResult.user_id == user_id,
            UserTestResult.test_id.in_(unique_ids),
        )
        if completed_after_utc is not None:
            results_query = results_query.where(UserTestResult.completed_at >= completed_after_utc)
        if completed_before_utc is not None:
            results_query = results_query.where(UserTestResult.completed_at < completed_before_utc)
        results_res = await db.execute(results_query)
        for value in list(results_res.scalars().all()):
            completed_ids.add(int(value))

        cases_query = select(CaseSolution.test_id).where(
            CaseSolution.user_id == user_id,
            CaseSolution.test_id.in_(unique_ids),
        )
        if completed_after_utc is not None:
            cases_query = cases_query.where(CaseSolution.created_at >= completed_after_utc)
        if completed_before_utc is not None:
            cases_query = cases_query.where(CaseSolution.created_at < completed_before_utc)
        cases_res = await db.execute(cases_query)
        for value in list(cases_res.scalars().all()):
            completed_ids.add(int(value))

        return completed_ids

    def _apply_final_level_up(
        self,
        profile: SoftSkillsProfile,
        target_difficulty: str,
    ) -> None:
        floor = self._next_level_floor_for_difficulty(target_difficulty)
        step = 8
        profile.communication_score = min(100.0, max(float(profile.communication_score or 0.0) + step, float(floor)))
        profile.emotional_intelligence_score = min(100.0, max(float(profile.emotional_intelligence_score or 0.0) + step, float(floor)))
        profile.critical_thinking_score = min(100.0, max(float(profile.critical_thinking_score or 0.0) + step, float(floor)))
        profile.time_management_score = min(100.0, max(float(profile.time_management_score or 0.0) + step, float(floor)))
        profile.leadership_score = min(100.0, max(float(profile.leadership_score or 0.0) + step, float(floor)))

    async def sync_plan_tracking(
        self,
        plan: DevelopmentPlan,
        user_id: int,
        db: AsyncSession,
        profile: Optional[SoftSkillsProfile] = None,
    ) -> Dict[str, Any]:
        content = plan.content
        if not isinstance(content, dict):
            content = {}

        materials = content.get("materials")
        if not isinstance(materials, list):
            materials = []
        tasks = content.get("tasks")
        if not isinstance(tasks, list):
            tasks = []

        changed = False

        tests_res = await db.execute(select(Test).where(Test.type != "simulation").order_by(Test.id.asc()))
        regular_tests = [t for t in list(tests_res.scalars().all()) if not self._is_final_test(t)]
        regular_test_ids: List[int] = []
        for t in regular_tests:
            try:
                test_id = int(t.id)
            except Exception:
                continue
            if test_id > 0:
                regular_test_ids.append(test_id)
        completed_before_plan = await self._get_completion_test_ids(
            user_id,
            regular_test_ids,
            db,
            completed_before=plan.generated_at,
        )
        raw_map = content.get("material_test_map")
        material_test_map = raw_map if isinstance(raw_map, dict) else {}
        computed_map = self._assign_tests_to_materials(
            materials,
            regular_tests,
            material_test_map,
            completed_test_ids=completed_before_plan,
        )
        if computed_map != material_test_map:
            material_test_map = computed_map
            content["material_test_map"] = material_test_map
            changed = True

        material_ids = [str(m.get("id", "")).strip() for m in materials if str(m.get("id", "")).strip()]
        raw_material_progress = content.get("material_progress")
        material_progress = raw_material_progress if isinstance(raw_material_progress, dict) else {}

        mapped_test_ids: List[int] = []
        for material_id in material_ids:
            value = material_test_map.get(material_id)
            try:
                test_id = int(value) if value is not None else None
            except Exception:
                test_id = None
            if test_id is not None and test_id > 0:
                mapped_test_ids.append(test_id)

        completed_test_ids = await self._get_completion_test_ids(
            user_id,
            mapped_test_ids,
            db,
            completed_after=plan.generated_at,
        )
        now_iso = datetime.now(timezone.utc).isoformat()

        normalized_material_progress: Dict[str, Dict[str, Any]] = {}
        for material_id in material_ids:
            entry = material_progress.get(material_id) if isinstance(material_progress.get(material_id), dict) else {}
            article_opened = bool(entry.get("article_opened"))
            article_opened_at = entry.get("article_opened_at")
            linked_test_id_raw = material_test_map.get(material_id)
            try:
                linked_test_id = int(linked_test_id_raw) if linked_test_id_raw is not None else None
            except Exception:
                linked_test_id = None

            test_completed = linked_test_id in completed_test_ids if linked_test_id is not None else False
            test_completed_at = entry.get("test_completed_at")
            if test_completed and not test_completed_at:
                test_completed_at = now_iso
            if not test_completed:
                test_completed_at = None

            normalized_material_progress[material_id] = {
                "linked_test_id": linked_test_id,
                "article_opened": article_opened,
                "article_opened_at": article_opened_at,
                "test_completed": test_completed,
                "test_completed_at": test_completed_at,
                "percentage": self._material_progress_percentage(article_opened, test_completed),
            }

        if normalized_material_progress != material_progress:
            material_progress = normalized_material_progress
            content["material_progress"] = material_progress
            changed = True

        progress = self._compute_components_progress(tasks, materials, material_progress)

        previous_final_stage = content.get("final_stage")
        if not isinstance(previous_final_stage, dict):
            previous_final_stage = {}
        previous_final_stage_snapshot = jsonable_encoder(previous_final_stage)

        final_stage = await self._ensure_final_stage_tests(content, db)
        final_test_id = final_stage.get("final_test_id")
        final_simulation_id = final_stage.get("final_simulation_id")
        completion_ids: List[int] = []
        try:
            if final_test_id is not None:
                completion_ids.append(int(final_test_id))
        except Exception:
            pass
        try:
            if final_simulation_id is not None:
                completion_ids.append(int(final_simulation_id))
        except Exception:
            pass
        completion_set = await self._get_completion_test_ids(
            user_id,
            completion_ids,
            db,
            completed_after=plan.generated_at,
        )

        final_test_completed = int(final_test_id) in completion_set if final_test_id is not None else False
        final_simulation_completed = int(final_simulation_id) in completion_set if final_simulation_id is not None else False

        final_stage["unlocked"] = bool(progress.get("percentage", 0) >= 100)
        final_stage["final_test_completed"] = final_test_completed
        final_stage["final_simulation_completed"] = final_simulation_completed
        final_stage["completed"] = bool(final_test_completed and final_simulation_completed)
        final_stage.setdefault("level_up_applied", False)
        final_stage["achievement_title"] = self._build_block_achievement_title(content)

        achievements = content.get("block_achievements")
        if not isinstance(achievements, list):
            achievements = []

        if final_stage != previous_final_stage_snapshot:
            changed = True

        previous_achievements = content.get("block_achievements")
        if not isinstance(previous_achievements, list):
            previous_achievements = []
        if achievements != previous_achievements:
            changed = True

        content["final_stage"] = final_stage
        content["block_achievements"] = achievements

        if changed:
            plan.content = jsonable_encoder(content)
            flag_modified(plan, "content")
            await db.commit()
            await db.refresh(plan)

        return {
            "material_progress": material_progress,
            "progress": progress,
            "final_stage": final_stage,
            "block_achievements": achievements,
        }

    async def advance_to_next_level(
        self,
        user_id: int,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        plan = await self.get_active_plan(user_id, db)
        if plan is None:
            raise ValueError("Р Р€ Р Р†Р В°РЎРѓ Р Р…Р ВµРЎвЂљ Р В°Р С”РЎвЂљР С‘Р Р†Р Р…Р С•Р С–Р С• Р С—Р В»Р В°Р Р…Р В° РЎР‚Р В°Р В·Р Р†Р С‘РЎвЂљР С‘РЎРЏ")

        profile_res = await db.execute(select(SoftSkillsProfile).where(SoftSkillsProfile.user_id == user_id))
        profile = profile_res.scalar_one_or_none()
        if profile is None:
            raise ValueError("Р СџРЎР‚Р С•РЎвЂћР С‘Р В»РЎРЉ Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р…. Р РЋР Р…Р В°РЎвЂЎР В°Р В»Р В° Р С—РЎР‚Р С•Р в„–Р Т‘Р С‘РЎвЂљР Вµ РЎвЂљР ВµРЎРѓРЎвЂљ Р С‘Р В»Р С‘ Р С•РЎвЂљР С—РЎР‚Р В°Р Р†РЎРЉРЎвЂљР Вµ РЎРѓР С•Р С•Р В±РЎвЂ°Р ВµР Р…Р С‘Р Вµ Р Р† РЎвЂЎР В°РЎвЂљ.")

        tracking = await self.sync_plan_tracking(
            plan=plan,
            user_id=user_id,
            db=db,
            profile=profile,
        )
        await db.refresh(plan)

        content = plan.content if isinstance(plan.content, dict) else {}
        final_stage = tracking.get("final_stage")
        if not isinstance(final_stage, dict):
            final_stage = {}

        if not bool(final_stage.get("unlocked")):
            raise ValueError("Р РЋР Р…Р В°РЎвЂЎР В°Р В»Р В° Р Т‘Р С•Р Р†Р ВµР Т‘Р С‘РЎвЂљР Вµ Р С—РЎР‚Р С•Р С–РЎР‚Р ВµРЎРѓРЎРѓ Р С—Р В»Р В°Р Р…Р В° Р Т‘Р С• 100%.")
        if not bool(final_stage.get("completed")):
            raise ValueError("Р РЋР Р…Р В°РЎвЂЎР В°Р В»Р В° Р В·Р В°Р Р†Р ВµРЎР‚РЎв‚¬Р С‘РЎвЂљР Вµ Р С•Р В±Р В° РЎвЂћР С‘Р Р…Р В°Р В»РЎРЉР Р…РЎвЂ№РЎвЂ¦ Р В·Р В°Р Т‘Р В°Р Р…Р С‘РЎРЏ.")

        target_difficulty = str(content.get("target_difficulty") or "beginner")
        achievement_title = self._build_block_achievement_title(content)
        level_up_was_applied = bool(final_stage.get("level_up_applied"))

        if not level_up_was_applied:
            now_iso = datetime.now(timezone.utc).isoformat()
            self._apply_final_level_up(profile, target_difficulty)
            db.add(
                ProfileHistory(
                    user_id=user_id,
                    profile_id=profile.id,
                    communication_score=float(profile.communication_score or 0.0),
                    emotional_intelligence_score=float(profile.emotional_intelligence_score or 0.0),
                    critical_thinking_score=float(profile.critical_thinking_score or 0.0),
                    time_management_score=float(profile.time_management_score or 0.0),
                    leadership_score=float(profile.leadership_score or 0.0),
                )
            )

            final_stage["level_up_applied"] = True
            final_stage["completed_at"] = now_iso
            final_stage["achievement_title"] = achievement_title

            achievements = content.get("block_achievements")
            if not isinstance(achievements, list):
                achievements = []
            achievement_id = f"block_{plan.id}_{target_difficulty}"
            if not any(str(item.get("id")) == achievement_id for item in achievements if isinstance(item, dict)):
                achievements.append(
                    {
                        "id": achievement_id,
                        "title": achievement_title,
                        "achieved_at": now_iso,
                    }
                )

            content["final_stage"] = final_stage
            content["block_achievements"] = achievements
            plan.content = jsonable_encoder(content)
            flag_modified(plan, "content")
            await db.commit()
            await db.refresh(plan)
            await db.refresh(profile)

        new_plan = await self._generate_new_plan(
            user_id=user_id,
            profile=profile,
            db=db,
        )
        await db.commit()
        await db.refresh(new_plan)

        return {
            "level_up_applied": True,
            "already_applied": level_up_was_applied,
            "new_plan_generated": True,
            "new_plan_id": int(new_plan.id),
            "achievement_title": achievement_title,
        }

    def _curated_material_library(self) -> List[Dict[str, str]]:
        return [
            {
                "id": "ru_4brain_comm_communication",
                "title": "Р В­РЎвЂћРЎвЂћР ВµР С”РЎвЂљР С‘Р Р†Р Р…Р С•Р Вµ Р С•Р В±РЎвЂ°Р ВµР Р…Р С‘Р Вµ: Р Р†Р ВµРЎР‚Р В±Р В°Р В»РЎРЉР Р…Р В°РЎРЏ Р С‘ Р Р…Р ВµР Р†Р ВµРЎР‚Р В±Р В°Р В»РЎРЉР Р…Р В°РЎРЏ Р С”Р С•Р СР СРЎС“Р Р…Р С‘Р С”Р В°РЎвЂ Р С‘РЎРЏ",
                "url": "https://4brain.ru/management/communication.php",
                "type": "article",
                "skill": "communication",
            },
            {
                "id": "ru_4brain_comm_nonverbal",
                "title": "Р СњР ВµР Р†Р ВµРЎР‚Р В±Р В°Р В»РЎРЉР Р…Р В°РЎРЏ Р С”Р С•Р СР СРЎС“Р Р…Р С‘Р С”Р В°РЎвЂ Р С‘РЎРЏ",
                "url": "https://4brain.ru/nonverbal/",
                "type": "article",
                "skill": "communication",
            },
            {
                "id": "ru_4brain_comm_listening",
                "title": "Р СћР ВµРЎвЂ¦Р Р…Р С‘Р С”Р С‘ Р В°Р С”РЎвЂљР С‘Р Р†Р Р…Р С•Р С–Р С• (Р С–Р В»РЎС“Р В±Р С•Р С”Р С•Р С–Р С•) РЎРѓР В»РЎС“РЎв‚¬Р В°Р Р…Р С‘РЎРЏ",
                "url": "https://4brain.ru/blog/glubokoe-slushanie/",
                "type": "article",
                "skill": "communication",
            },
            {
                "id": "ru_4brain_comm_negotiation",
                "title": "Р вЂ™Р ВµР Т‘Р ВµР Р…Р С‘Р Вµ Р С—Р ВµРЎР‚Р ВµР С–Р С•Р Р†Р С•РЎР‚Р С•Р Р†: Р С•РЎРѓР Р…Р С•Р Р†РЎвЂ№ Р С‘ РЎРѓРЎвЂљРЎР‚РЎС“Р С”РЎвЂљРЎС“РЎР‚Р В°",
                "url": "https://4brain.ru/peregovory/",
                "type": "article",
                "skill": "communication",
            },
            {
                "id": "ru_4brain_comm_rhetoric",
                "title": "Р С›РЎР‚Р В°РЎвЂљР С•РЎР‚РЎРѓР С”Р С•Р Вµ Р С‘РЎРѓР С”РЎС“РЎРѓРЎРѓРЎвЂљР Р†Р С•: РЎС“РЎР‚Р С•Р С”Р С‘ РЎР‚Р С‘РЎвЂљР С•РЎР‚Р С‘Р С”Р С‘",
                "url": "https://4brain.ru/oratorskoe-iskusstvo/",
                "type": "article",
                "skill": "communication",
            },
            {
                "id": "ru_stepik_comm_effective",
                "title": "Р СњР В°Р Р†РЎвЂ№Р С”Р С‘ РЎРЊРЎвЂћРЎвЂћР ВµР С”РЎвЂљР С‘Р Р†Р Р…Р С•Р в„– Р С”Р С•Р СР СРЎС“Р Р…Р С‘Р С”Р В°РЎвЂ Р С‘Р С‘",
                "url": "https://stepik.org/course/205042/promo",
                "type": "course",
                "skill": "communication",
            },
            {
                "id": "ru_stepik_comm_business",
                "title": "Р вЂќР ВµР В»Р С•Р Р†РЎвЂ№Р Вµ Р С”Р С•Р СР СРЎС“Р Р…Р С‘Р С”Р В°РЎвЂ Р С‘Р С‘",
                "url": "https://stepik.org/course/87737/promo",
                "type": "course",
                "skill": "communication",
            },
            {
                "id": "ru_openedu_teamwork",
                "title": "Р С™Р С•Р СР В°Р Р…Р Т‘Р Р…Р В°РЎРЏ РЎР‚Р В°Р В±Р С•РЎвЂљР В°",
                "url": "https://openedu.ru/course/ITMOUniversity/TEAMWORK/",
                "type": "course",
                "skill": "communication",
            },
            {
                "id": "ru_4brain_ei_base",
                "title": "Р В­Р СР С•РЎвЂ Р С‘Р С•Р Р…Р В°Р В»РЎРЉР Р…РЎвЂ№Р в„– Р С‘Р Р…РЎвЂљР ВµР В»Р В»Р ВµР С”РЎвЂљ: Р С•РЎРѓР Р…Р С•Р Р†РЎвЂ№ Р С‘ РЎС“Р С—РЎР‚Р В°Р В¶Р Р…Р ВµР Р…Р С‘РЎРЏ",
                "url": "https://4brain.ru/emotion/",
                "type": "article",
                "skill": "emotional_intelligence",
            },
            {
                "id": "ru_4brain_ei_article",
                "title": "Р С™Р В°Р С” РЎР‚Р В°Р В·Р Р†Р С‘РЎвЂљРЎРЉ РЎРЊР СР С•РЎвЂ Р С‘Р С•Р Р…Р В°Р В»РЎРЉР Р…РЎвЂ№Р в„– Р С‘Р Р…РЎвЂљР ВµР В»Р В»Р ВµР С”РЎвЂљ",
                "url": "https://4brain.ru/blog/emotional-intellect/",
                "type": "article",
                "skill": "emotional_intelligence",
            },
            {
                "id": "ru_stepik_ei",
                "title": "Р В­Р СР С•РЎвЂ Р С‘Р С•Р Р…Р В°Р В»РЎРЉР Р…РЎвЂ№Р в„– Р С‘Р Р…РЎвЂљР ВµР В»Р В»Р ВµР С”РЎвЂљ: Р С”Р В»РЎР‹РЎвЂЎ Р С” РЎС“РЎРѓР С—Р ВµРЎвЂ¦РЎС“",
                "url": "https://stepik.org/course/133690/promo",
                "type": "course",
                "skill": "emotional_intelligence",
            },
            {
                "id": "ru_4brain_ct_base",
                "title": "Р С™РЎР‚Р С‘РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С•Р Вµ Р СРЎвЂ№РЎв‚¬Р В»Р ВµР Р…Р С‘Р Вµ: РЎвЂЎРЎвЂљР С• РЎРЊРЎвЂљР С• Р С‘ Р С”Р В°Р С” РЎР‚Р В°Р В·Р Р†Р С‘Р Р†Р В°РЎвЂљРЎРЉ",
                "url": "https://4brain.ru/critical/",
                "type": "article",
                "skill": "critical_thinking",
            },
            {
                "id": "ru_4brain_ct_skills",
                "title": "Р С™РЎР‚Р С‘РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С•Р Вµ Р СРЎвЂ№РЎв‚¬Р В»Р ВµР Р…Р С‘Р Вµ: Р Р…Р В°Р Р†РЎвЂ№Р С”Р С‘ Р С‘ РЎРѓР Р†Р С•Р в„–РЎРѓРЎвЂљР Р†Р В°",
                "url": "https://4brain.ru/critical/navyk.php",
                "type": "article",
                "skill": "critical_thinking",
            },
            {
                "id": "ru_stepik_ct",
                "title": "Р С™РЎР‚Р С‘РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С•Р Вµ Р СРЎвЂ№РЎв‚¬Р В»Р ВµР Р…Р С‘Р Вµ",
                "url": "https://stepik.org/course/63700/promo",
                "type": "course",
                "skill": "critical_thinking",
            },
            {
                "id": "ru_postnauka_ct_video",
                "title": "Р С™РЎР‚Р С‘РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С•Р Вµ Р СРЎвЂ№РЎв‚¬Р В»Р ВµР Р…Р С‘Р Вµ",
                "url": "https://postnauka.ru/tv/155334",
                "type": "video",
                "skill": "critical_thinking",
            },
            {
                "id": "ru_4brain_tm_base",
                "title": "Р СћР В°Р в„–Р С-Р СР ВµР Р…Р ВµР Т‘Р В¶Р СР ВµР Р…РЎвЂљ: РЎС“Р С—РЎР‚Р В°Р Р†Р В»Р ВµР Р…Р С‘Р Вµ Р Р†РЎР‚Р ВµР СР ВµР Р…Р ВµР С",
                "url": "https://4brain.ru/time/",
                "type": "article",
                "skill": "time_management",
            },
            {
                "id": "ru_4brain_tm_basics",
                "title": "Р СћР В°Р в„–Р С-Р СР ВµР Р…Р ВµР Т‘Р В¶Р СР ВµР Р…РЎвЂљ: Р С•РЎРѓР Р…Р С•Р Р†РЎвЂ№",
                "url": "https://4brain.ru/time/osnovy.php",
                "type": "article",
                "skill": "time_management",
            },
            {
                "id": "ru_4brain_tm_psy",
                "title": "Р СџРЎРѓР С‘РЎвЂ¦Р С•Р В»Р С•Р С–Р С‘РЎвЂЎР ВµРЎРѓР С”Р С‘Р Вµ Р В°РЎРѓР С—Р ВµР С”РЎвЂљРЎвЂ№ РЎвЂљР В°Р в„–Р С-Р СР ВµР Р…Р ВµР Т‘Р В¶Р СР ВµР Р…РЎвЂљР В°",
                "url": "https://4brain.ru/blog/psihologiya-taym-menedzhmenta/",
                "type": "article",
                "skill": "time_management",
            },
            {
                "id": "ru_openedu_tm_course",
                "title": "Р С›Р Р…Р В»Р В°Р в„–Р Р…-Р С”РЎС“РЎР‚РЎРѓ: Р СћР В°Р в„–Р С-Р СР ВµР Р…Р ВµР Т‘Р В¶Р СР ВµР Р…РЎвЂљ",
                "url": "https://openedu.ru/course/misis/TMNG/",
                "type": "course",
                "skill": "time_management",
            },
            {
                "id": "ru_stepik_tm",
                "title": "Р СћР В°Р в„–Р С-Р СР ВµР Р…Р ВµР Т‘Р В¶Р СР ВµР Р…РЎвЂљ",
                "url": "https://stepik.org/course/102186/promo",
                "type": "course",
                "skill": "time_management",
            },
            {
                "id": "ru_4brain_lead_base",
                "title": "Р вЂєР С‘Р Т‘Р ВµРЎР‚РЎРѓРЎвЂљР Р†Р С•: Р В±Р В°Р В·Р С•Р Р†РЎвЂ№Р Вµ Р С—РЎР‚Р С‘Р Р…РЎвЂ Р С‘Р С—РЎвЂ№ Р С‘ Р С—Р С•Р Т‘РЎвЂ¦Р С•Р Т‘РЎвЂ№",
                "url": "https://4brain.ru/liderstvo/",
                "type": "article",
                "skill": "leadership",
            },
            {
                "id": "ru_4brain_lead_course",
                "title": "Р вЂєР С‘Р Т‘Р ВµРЎР‚РЎРѓРЎвЂљР Р†Р С• Р С‘ Р СР С•РЎвЂљР С‘Р Р†Р В°РЎвЂ Р С‘РЎРЏ: Р С•РЎРѓР Р…Р С•Р Р†РЎвЂ№",
                "url": "https://4brain.ru/management/leadership.php",
                "type": "article",
                "skill": "leadership",
            },
            {
                "id": "ru_4brain_lead_practice",
                "title": "Р С™Р В°Р С” Р В±РЎвЂ№РЎвЂљРЎРЉ Р В»Р С‘Р Т‘Р ВµРЎР‚Р С•Р С: Р С—РЎР‚Р В°Р С”РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С‘Р Вµ РЎРѓР С•Р Р†Р ВµРЎвЂљРЎвЂ№",
                "url": "https://4brain.ru/blog/kak-byt-liderom/",
                "type": "article",
                "skill": "leadership",
            },
            {
                "id": "ru_openedu_lead_course",
                "title": "Р вЂєР С‘Р Т‘Р ВµРЎР‚РЎРѓРЎвЂљР Р†Р С• Р С‘ Р С”Р С•Р СР В°Р Р…Р Т‘Р С•Р С•Р В±РЎР‚Р В°Р В·Р С•Р Р†Р В°Р Р…Р С‘Р Вµ",
                "url": "https://openedu.ru/course/mephi/mephi_lfkpt/",
                "type": "course",
                "skill": "leadership",
            },
            {
                "id": "ru_stepik_lead_team",
                "title": "Р вЂєР С‘Р Т‘Р ВµРЎР‚РЎРѓРЎвЂљР Р†Р С• Р С‘ Р С”Р С•Р СР В°Р Р…Р Т‘Р С•Р С•Р В±РЎР‚Р В°Р В·Р С•Р Р†Р В°Р Р…Р С‘Р Вµ",
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
        if "РЎвЂљР В°Р в„–Р С" in w or "Р Р†РЎР‚Р ВµР СР ВµР Р…" in w:
            return "time_management"
        if "Р С”РЎР‚Р С‘РЎвЂљ" in w:
            return "critical_thinking"
        if "Р С”Р С•Р СР СРЎС“Р Р…Р С‘Р С”" in w or "Р С•Р В±РЎвЂ°Р ВµР Р…" in w:
            return "communication"
        if "РЎРЊР СР С•РЎвЂ Р С‘Р С•Р Р…" in w:
            return "emotional_intelligence"
        if "Р В»Р С‘Р Т‘Р ВµРЎР‚" in w:
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

    async def mark_material_article_open(
        self,
        user_id: int,
        plan_id: int,
        material_id: str,
        db: AsyncSession,
    ) -> DevelopmentPlan:
        result = await db.execute(
            select(DevelopmentPlan)
            .where(
                and_(
                    DevelopmentPlan.id == plan_id,
                    DevelopmentPlan.user_id == user_id,
                    DevelopmentPlan.is_archived == False,
                )
            )
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            raise ValueError(f"Active plan {plan_id} not found for user {user_id}")

        content = plan.content
        if not isinstance(content, dict):
            content = {}

        materials = content.get("materials")
        if not isinstance(materials, list):
            materials = []
            content["materials"] = materials

        if not any(str(material.get("id")) == str(material_id) for material in materials if isinstance(material, dict)):
            raise ValueError(f"Material {material_id} not found in plan {plan_id}")

        material_progress = content.get("material_progress")
        if not isinstance(material_progress, dict):
            material_progress = {}
            content["material_progress"] = material_progress

        entry = material_progress.get(str(material_id))
        if not isinstance(entry, dict):
            entry = {}
        entry["article_opened"] = True
        entry.setdefault("article_opened_at", datetime.now(timezone.utc).isoformat())
        entry["percentage"] = self._material_progress_percentage(
            bool(entry.get("article_opened")),
            bool(entry.get("test_completed")),
        )
        material_progress[str(material_id)] = entry

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
        _ = db
        content = plan.content
        if not isinstance(content, dict):
            return False

        final_stage = content.get("final_stage")
        if not isinstance(final_stage, dict):
            final_stage = {}

        # Prevent plan switching while user is still finishing the current block.
        if not bool(final_stage.get("level_up_applied")):
            return False

        current_target_difficulty = self._resolve_target_difficulty(profile)
        plan_target_difficulty = self._infer_plan_difficulty(content)
        if plan_target_difficulty and plan_target_difficulty != current_target_difficulty:
            logger.info(
                "Plan %s difficulty '%s' differs from current '%s' after block completion. Triggering regeneration.",
                plan.id,
                plan_target_difficulty,
                current_target_difficulty,
            )
            return True

        logger.info(
            "Plan %s block is completed (level_up_applied=true). Triggering regeneration for next block.",
            plan.id,
        )
        return True
    
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
        achievement_plans_result = await db.execute(
            select(DevelopmentPlan)
            .where(DevelopmentPlan.user_id == user_id)
            .order_by(desc(DevelopmentPlan.generated_at))
            .limit(100)
        )
        achievement_plans = achievement_plans_result.scalars().all()        
        # Step 4: Generate plan using LLM (Requirements 3.2, 3.3, 3.4)
        yandex_folder_id = str(settings.YANDEX_FOLDER_ID or "").strip()
        yandex_api_key = str(settings.YANDEX_API_KEY or "").strip()
        try:
            if not yandex_folder_id or not yandex_api_key:
                raise RuntimeError("Yandex LLM configuration is incomplete")
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
                        title="Р С›РЎРѓР Р…Р С•Р Р†РЎвЂ№ Р С”Р С•Р СР СРЎС“Р Р…Р С‘Р С”Р В°РЎвЂ Р С‘Р С‘: Р В°Р С”РЎвЂљР С‘Р Р†Р Р…Р С•Р Вµ РЎРѓР В»РЎС“РЎв‚¬Р В°Р Р…Р С‘Р Вµ",
                        url="https://4brain.ru/blog/glubokoe-slushanie/",
                        type="article",
                        skill="communication",
                        difficulty=target_difficulty,
                    ),
                    MaterialItem(
                        id="mat_ei_basics",
                        title="Р В­Р СР С•РЎвЂ Р С‘Р С•Р Р…Р В°Р В»РЎРЉР Р…РЎвЂ№Р в„– Р С‘Р Р…РЎвЂљР ВµР В»Р В»Р ВµР С”РЎвЂљ: Р В±Р В°Р В·Р С•Р Р†РЎвЂ№Р Вµ Р С—РЎР‚Р С‘Р Р…РЎвЂ Р С‘Р С—РЎвЂ№",
                        url="https://4brain.ru/emotion/",
                        type="article",
                        skill="emotional_intelligence",
                        difficulty=target_difficulty,
                    ),
                    MaterialItem(
                        id="mat_critical_thinking_basics",
                        title="Р С™РЎР‚Р С‘РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С•Р Вµ Р СРЎвЂ№РЎв‚¬Р В»Р ВµР Р…Р С‘Р Вµ: Р С”Р В°Р С” Р В·Р В°Р Т‘Р В°Р Р†Р В°РЎвЂљРЎРЉ Р С—РЎР‚Р В°Р Р†Р С‘Р В»РЎРЉР Р…РЎвЂ№Р Вµ Р Р†Р С•Р С—РЎР‚Р С•РЎРѓРЎвЂ№",
                        url="https://4brain.ru/critical/",
                        type="article",
                        skill="critical_thinking",
                        difficulty=target_difficulty,
                    ),
                ],
                tasks=[
                    TaskItem(
                        id="task_reflect_1",
                        description="Р СџР С•РЎРѓР В»Р Вµ Р Т‘Р С‘Р В°Р В»Р С•Р С–Р В° Р В·Р В°Р С—Р С‘РЎв‚¬Р С‘РЎвЂљР Вµ 3 Р С—РЎС“Р Р…Р С”РЎвЂљР В°: РЎвЂЎРЎвЂљР С• Р С—Р С•Р В»РЎС“РЎвЂЎР С‘Р В»Р С•РЎРѓРЎРЉ, РЎвЂЎРЎвЂљР С• Р СР С•Р В¶Р Р…Р С• РЎС“Р В»РЎС“РЎвЂЎРЎв‚¬Р С‘РЎвЂљРЎРЉ, Р С”Р В°Р С”Р С•Р в„– РЎРѓР В»Р ВµР Т‘РЎС“РЎР‹РЎвЂ°Р С‘Р в„– РЎв‚¬Р В°Р С–.",
                        skill="communication",
                        status="pending",
                        completed_at=None,
                    ),
                    TaskItem(
                        id="task_ei_1",
                        description="Р вЂ™ РЎРѓР В»Р ВµР Т‘РЎС“РЎР‹РЎвЂ°Р ВµР в„– РЎРѓР В»Р С•Р В¶Р Р…Р С•Р в„– РЎРѓР С‘РЎвЂљРЎС“Р В°РЎвЂ Р С‘Р С‘ Р С—Р С•Р С—РЎР‚Р С•Р В±РЎС“Р в„–РЎвЂљР Вµ Р Р…Р В°Р В·Р Р†Р В°РЎвЂљРЎРЉ РЎРЊР СР С•РЎвЂ Р С‘Р С‘ РЎРѓР С•Р В±Р ВµРЎРѓР ВµР Т‘Р Р…Р С‘Р С”Р В° Р С‘ РЎС“РЎвЂљР С•РЎвЂЎР Р…Р С‘РЎвЂљРЎРЉ Р С‘РЎвЂ¦ Р Р†Р С•Р С—РЎР‚Р С•РЎРѓР С•Р С.",
                        skill="emotional_intelligence",
                        status="pending",
                        completed_at=None,
                    ),
                    TaskItem(
                        id="task_ct_1",
                        description="Р СџР ВµРЎР‚Р ВµР Т‘ РЎР‚Р ВµРЎв‚¬Р ВµР Р…Р С‘Р ВµР С Р В·Р В°Р Т‘Р В°РЎвЂЎР С‘ РЎРѓРЎвЂћР С•РЎР‚Р СРЎС“Р В»Р С‘РЎР‚РЎС“Р в„–РЎвЂљР Вµ 5 РЎС“РЎвЂљР С•РЎвЂЎР Р…РЎРЏРЎР‹РЎвЂ°Р С‘РЎвЂ¦ Р Р†Р С•Р С—РЎР‚Р С•РЎРѓР С•Р Р† (РЎвЂЎРЎвЂљР С• Р Р…Р ВµР С‘Р В·Р Р†Р ВµРЎРѓРЎвЂљР Р…Р С•, Р С”Р В°Р С”Р С‘Р Вµ Р С•Р С–РЎР‚Р В°Р Р…Р С‘РЎвЂЎР ВµР Р…Р С‘РЎРЏ).",
                        skill="critical_thinking",
                        status="pending",
                        completed_at=None,
                    ),
                ],
                recommended_tests=[
                    TestRecommendation(
                        test_id=0,
                        title="Р вЂєРЎР‹Р В±Р С•Р в„– Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р Р…РЎвЂ№Р в„– РЎвЂљР ВµРЎРѓРЎвЂљ",
                        reason="Р СџР С•Р С”Р В° РЎРѓР ВµРЎР‚Р Р†Р С‘РЎРѓ Р С–Р ВµР Р…Р ВµРЎР‚Р В°РЎвЂ Р С‘Р С‘ РЎР‚Р ВµР С”Р С•Р СР ВµР Р…Р Т‘Р В°РЎвЂ Р С‘Р в„– Р Р…Р ВµР Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р… РІР‚вЂќ Р С—РЎР‚Р С•Р в„–Р Т‘Р С‘РЎвЂљР Вµ РЎвЂљР ВµРЎРѓРЎвЂљРЎвЂ№ Р С‘Р В· РЎР‚Р В°Р В·Р Т‘Р ВµР В»Р В° 'Р СћР ВµРЎРѓРЎвЂљРЎвЂ№' Р Т‘Р В»РЎРЏ Р Р…Р В°Р С”Р С•Р С—Р В»Р ВµР Р…Р С‘РЎРЏ Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦.",
                    )
                ],
            )

        plan_content.materials = self._select_curated_materials(
            weaknesses=weaknesses,
            target_difficulty=target_difficulty,
            previous_plans=list(previous_plans),
        )

        plan_content.recommended_tests = await self._select_recommended_tests(
            user_id=user_id,
            weaknesses=weaknesses,
            target_difficulty=target_difficulty,
            db=db,
        )
        
        # Step 5: Validate material uniqueness (Requirement 4.5, Property 13)
        if previous_plans:
            most_recent_plan = previous_plans[0]
            if not self._check_material_uniqueness(plan_content, most_recent_plan):
                logger.warning(f"Generated plan for user {user_id} has less than 70% unique materials. Accepting anyway.")
        
        # Step 6: Save new plan (Requirement 3.5, Property 8)
        payload = plan_content.dict()
        payload["target_difficulty"] = target_difficulty
        payload["block_achievements"] = self._collect_block_achievements(achievement_plans)
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

    async def _select_recommended_tests(
        self,
        user_id: int,
        weaknesses: List[str],
        target_difficulty: str,
        db: AsyncSession,
    ) -> List[TestRecommendation]:
        query = await db.execute(select(Test).where(Test.type != "simulation").order_by(Test.id.asc()))
        tests = [t for t in list(query.scalars().all()) if not self._is_final_test(t)]
        if not tests:
            return []

        preferred_type = "case" if str(target_difficulty).lower() == "advanced" else "quiz"
        preferred = [t for t in tests if str(t.type).lower() == preferred_type]
        others = [t for t in tests if t not in preferred]
        tests = preferred + others

        all_test_ids: List[int] = []
        for t in tests:
            try:
                test_id = int(t.id)
            except Exception:
                continue
            if test_id > 0:
                all_test_ids.append(test_id)
        completed_test_ids = await self._get_completion_test_ids(
            user_id=user_id,
            test_ids=all_test_ids,
            db=db,
        )

        skill_keywords = self._skill_keywords()

        def _resolve_skill(weakness: str) -> Optional[str]:
            if not weakness:
                return None
            normalized = weakness.lower().replace("-", " ").replace("_", " ")
            for skill, keywords in skill_keywords.items():
                if any(keyword in normalized for keyword in keywords):
                    return skill
            return None

        tests_by_skill: Dict[str, List[Test]] = {skill: [] for skill in skill_keywords.keys()}
        for t in tests:
            hay = f"{t.title} {t.description}".lower()
            matched_skill: Optional[str] = None
            for skill, keywords in skill_keywords.items():
                if any(keyword in hay for keyword in keywords):
                    matched_skill = skill
                    break
            if matched_skill is not None:
                tests_by_skill[matched_skill].append(t)

        def _pick_from_candidates(candidates: List[Test], current: List[Test]) -> Optional[Test]:
            preferred_fresh = [
                t for t in candidates
                if t not in current and int(t.id) not in completed_test_ids
            ]
            if preferred_fresh:
                return preferred_fresh[0]
            fallback = [t for t in candidates if t not in current]
            if fallback:
                return fallback[0]
            return None

        picked: List[Test] = []
        for w in weaknesses:
            skill = _resolve_skill(w)
            if not skill:
                continue
            selected = _pick_from_candidates(tests_by_skill.get(skill, []), picked)
            if selected is not None:
                picked.append(selected)
            if len(picked) >= 3:
                break

        for t in tests:
            if len(picked) >= 3:
                break
            if t in picked:
                continue
            if int(t.id) in completed_test_ids:
                continue
            picked.append(t)

        for t in tests:
            if len(picked) >= 3:
                break
            if t not in picked:
                picked.append(t)

        reason = "Р В Р ВµР С”Р С•Р СР ВµР Р…Р Т‘РЎС“Р ВµР С Р С—РЎР‚Р С•Р в„–РЎвЂљР С‘ РЎвЂљР ВµРЎРѓРЎвЂљРЎвЂ№, РЎвЂЎРЎвЂљР С•Р В±РЎвЂ№ РЎРѓР С•Р В±РЎР‚Р В°РЎвЂљРЎРЉ Р В±Р С•Р В»РЎРЉРЎв‚¬Р Вµ Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦ Р С‘ РЎС“Р В»РЎС“РЎвЂЎРЎв‚¬Р С‘РЎвЂљРЎРЉ РЎРѓР В»Р В°Р В±РЎвЂ№Р Вµ Р Р…Р В°Р Р†РЎвЂ№Р С”Р С‘." if weaknesses else "Р В Р ВµР С”Р С•Р СР ВµР Р…Р Т‘РЎС“Р ВµР С Р С—РЎР‚Р С•Р в„–РЎвЂљР С‘ РЎвЂљР ВµРЎРѓРЎвЂљРЎвЂ№ Р Т‘Р В»РЎРЏ Р Р…Р В°Р С”Р С•Р С—Р В»Р ВµР Р…Р С‘РЎРЏ Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦." 
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
            ("Р СћР В°Р в„–Р С-Р СР ВµР Р…Р ВµР Т‘Р В¶Р СР ВµР Р…РЎвЂљ", profile.time_management_score),
            ("Р С™РЎР‚Р С‘РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С•Р Вµ Р СРЎвЂ№РЎв‚¬Р В»Р ВµР Р…Р С‘Р Вµ", profile.critical_thinking_score),
            ("Р С™Р С•Р СР СРЎС“Р Р…Р С‘Р С”Р В°РЎвЂ Р С‘РЎРЏ", profile.communication_score),
            ("Р В­Р СР С•РЎвЂ Р С‘Р С•Р Р…Р В°Р В»РЎРЉР Р…РЎвЂ№Р в„– Р С‘Р Р…РЎвЂљР ВµР В»Р В»Р ВµР С”РЎвЂљ", profile.emotional_intelligence_score),
            ("Р вЂєР С‘Р Т‘Р ВµРЎР‚РЎРѓРЎвЂљР Р†Р С•", profile.leadership_score)
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

