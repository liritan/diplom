"""
Test script for PlanService implementation.
Tests basic functionality without requiring database connection.
"""

import asyncio
from datetime import datetime, timedelta
from app.services.plan_service import PlanService
from app.models.profile import SoftSkillsProfile, DevelopmentPlan
from app.schemas.plan import DevelopmentPlanContent, MaterialItem, TaskItem, TestRecommendation


def test_identify_weaknesses():
    """Test weakness identification from profile."""
    print("\n=== Testing _identify_weaknesses ===")
    
    service = PlanService()
    
    # Create a mock profile
    profile = SoftSkillsProfile(
        id=1,
        user_id=1,
        communication_score=85.0,
        emotional_intelligence_score=70.0,
        critical_thinking_score=60.0,
        time_management_score=45.0,
        leadership_score=75.0
    )
    
    # Test weakness identification
    weaknesses = asyncio.run(service._identify_weaknesses(profile))
    
    print(f"Profile scores:")
    print(f"  Communication: {profile.communication_score}")
    print(f"  Emotional Intelligence: {profile.emotional_intelligence_score}")
    print(f"  Critical Thinking: {profile.critical_thinking_score}")
    print(f"  Time Management: {profile.time_management_score}")
    print(f"  Leadership: {profile.leadership_score}")
    print(f"\nIdentified weaknesses (bottom 3): {weaknesses}")
    
    # Verify weaknesses are the bottom 3 scores
    assert "Time Management" in weaknesses, "Time Management should be a weakness"
    assert "Critical Thinking" in weaknesses, "Critical Thinking should be a weakness"
    assert len(weaknesses) == 3, "Should identify exactly 3 weaknesses"
    
    print("✓ Weakness identification works correctly")


def test_check_material_uniqueness():
    """Test material uniqueness checking."""
    print("\n=== Testing _check_material_uniqueness ===")
    
    service = PlanService()
    
    # Create previous plan with some materials
    previous_plan = DevelopmentPlan(
        id=1,
        user_id=1,
        generated_at=datetime.utcnow() - timedelta(days=10),
        is_archived=False,
        content={
            "weaknesses": ["Time Management"],
            "materials": [
                {"id": "mat_1", "title": "Material 1", "url": "http://example.com/1", "type": "article", "skill": "time_management", "diffic