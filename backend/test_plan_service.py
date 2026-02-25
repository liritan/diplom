"""
Smoke tests for PlanService helper methods.

This script is intentionally framework-free so it can run with:
`python test_plan_service.py`
"""

import asyncio
from datetime import datetime, timedelta, timezone

from app.db.base import DevelopmentPlan, SoftSkillsProfile
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


def main():
    tests = [
        test_identify_weaknesses,
        test_check_material_uniqueness,
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
