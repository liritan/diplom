"""
Smoke tests for PlanService helper methods.

This script is intentionally framework-free so it can run with:
`python test_plan_service.py`
"""

import asyncio
from datetime import datetime, timedelta, timezone

from app.db.base import DevelopmentPlan, SoftSkillsProfile, Test
from app.schemas.plan import (
    DevelopmentPlanContent,
    MaterialItem,
    TaskItem,
    TestRecommendation,
)
from app.services.plan_service import PlanService


def _build_content(material_ids):
    return DevelopmentPlanContent(
        weaknesses=["time_management"],
        materials=[
            MaterialItem(
                id=material_id,
                title=f"Material {idx}",
                url=f"https://example.com/{material_id}",
                type="article",
                skill="time_management",
                difficulty="beginner",
            )
            for idx, material_id in enumerate(material_ids, start=1)
        ],
        tasks=[
            TaskItem(
                id="task_1",
                description="Complete one exercise",
                skill="time_management",
            )
        ],
        recommended_tests=[
            TestRecommendation(
                test_id=1,
                title="Baseline Test",
                reason="Track progress",
            )
        ],
    )


def test_identify_weaknesses():
    service = PlanService()
    profile = SoftSkillsProfile(
        id=1,
        user_id=1,
        communication_score=85.0,
        emotional_intelligence_score=70.0,
        critical_thinking_score=60.0,
        time_management_score=45.0,
        leadership_score=75.0,
    )

    weaknesses = asyncio.run(service._identify_weaknesses(profile))

    assert len(weaknesses) == 3, "Expected exactly 3 weaknesses"
    assert all(isinstance(item, str) and item for item in weaknesses), "Weakness names must be non-empty strings"


def test_check_material_uniqueness():
    service = PlanService()
    previous_plan = DevelopmentPlan(
        id=1,
        user_id=1,
        generated_at=datetime.now(timezone.utc) - timedelta(days=7),
        is_archived=False,
        content={
            "weaknesses": ["time_management"],
            "materials": [
                {"id": "mat_1"},
                {"id": "mat_2"},
            ],
            "tasks": [],
            "recommended_tests": [],
        },
    )

    unique_enough = _build_content(["mat_1", "mat_3", "mat_4", "mat_5"])
    not_unique_enough = _build_content(["mat_1", "mat_2", "mat_3"])

    assert service._check_material_uniqueness(unique_enough, previous_plan) is True
    assert service._check_material_uniqueness(not_unique_enough, previous_plan) is False


def test_assign_tests_to_materials_avoids_repeats_with_skill_alternatives():
    service = PlanService()

    materials = [
        {"id": "mat_comm_1", "skill": "communication"},
        {"id": "mat_lead_1", "skill": "leadership"},
    ]
    tests = [
        Test(id=1, title="Communication: baseline", description="", type="quiz"),
        Test(id=2, title="Communication: practice", description="", type="quiz"),
        Test(id=3, title="Leadership: baseline", description="", type="quiz"),
    ]
    existing_map = {
        "mat_comm_1": 1,
        "mat_lead_1": 3,
    }

    mapping = service._assign_tests_to_materials(
        materials=materials,
        tests=tests,
        existing_map=existing_map,
        completed_test_ids={1, 3},
    )

    assert mapping.get("mat_comm_1") == 2
    assert mapping.get("mat_lead_1") == 3


def test_collect_block_achievements_merges_history():
    service = PlanService()
    plans = [
        DevelopmentPlan(
            id=10,
            user_id=1,
            generated_at=datetime.now(timezone.utc) - timedelta(days=2),
            is_archived=True,
            content={
                "target_difficulty": "beginner",
                "block_achievements": [
                    {"id": "block_10_beginner", "title": "Блок 1", "achieved_at": "2026-01-10T10:00:00+00:00"},
                ],
            },
        ),
        DevelopmentPlan(
            id=11,
            user_id=1,
            generated_at=datetime.now(timezone.utc) - timedelta(days=1),
            is_archived=True,
            content={
                "target_difficulty": "intermediate",
                "final_stage": {
                    "level_up_applied": True,
                    "achievement_title": "Блок 2",
                    "completed_at": "2026-01-20T10:00:00+00:00",
                },
            },
        ),
    ]

    achievements = service._collect_block_achievements(plans)
    titles = [a.get("title") for a in achievements]

    assert "Блок 1" in titles
    assert "Блок 2" in titles


def main():
    tests = [
        test_identify_weaknesses,
        test_check_material_uniqueness,
        test_assign_tests_to_materials_avoids_repeats_with_skill_alternatives,
        test_collect_block_achievements_merges_history,
    ]

    failed = 0
    for test in tests:
        try:
            test()
            print(f"[OK] {test.__name__}")
        except Exception as exc:
            failed += 1
            print(f"[FAIL] {test.__name__}: {exc}")

    if failed:
        raise SystemExit(1)

    print("All plan service smoke tests passed.")


if __name__ == "__main__":
    main()
