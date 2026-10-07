import pytest
from soulsync.services.voice import check_private_memory_permission
from soulsync.db import SessionLocal

def test_permission_gate_flow():
    db = SessionLocal()
    # Verify function runs
    try:
        result = check_private_memory_permission(1, db)
        assert isinstance(result, bool)
    except Exception as e:
        pytest.fail(f"check_private_memory_permission raised {e}")
    db.close()
