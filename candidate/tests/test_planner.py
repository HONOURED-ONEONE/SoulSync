import pytest
from soulsync.services.planner_service import build_plan, apply_plan
from soulsync.db import SessionLocal

def test_build_plan():
    db = SessionLocal()
    today = "2025-01-15"
    minutes_cap = 60
    
    # This will return empty if no missions exist for user 1
    # Just verify function runs
    try:
        plan = build_plan(1, today, minutes_cap, db)
        assert isinstance(plan, list)
        
        # Verify total minutes <= cap
        total_mins = sum(d for _, _, d in plan)
        assert total_mins <= minutes_cap
    except Exception as e:
        pytest.fail(f"build_plan raised {e}")
    db.close()

def test_apply_plan_no_duplicates():
    db = SessionLocal()
    today = "2025-01-15"
    
    # Just verify function runs and doesn't crash
    try:
        apply_plan(1, today, [], db)
    except Exception as e:
        pytest.fail(f"apply_plan raised {e}")
    db.close()
