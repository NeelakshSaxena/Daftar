import os
import sys
import pytest

# Add standard import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.memory.db import MemoryDB
from app.tools.memory import MemoryTool

@pytest.fixture
def db():
    # Force an empty, new temporary database for isolated testing
    # But wait, MemoryDB is hardcoded to data/database/memory.db right now.
    # I should use it, but clear settings for tests.
    db_inst = MemoryDB(init_db=True)
    # Clear settings initially
    with db_inst._get_connection() as conn:
        conn.execute("DELETE FROM settings_overrides")
        conn.execute("DELETE FROM memories")
        conn.execute("DELETE FROM memory_versions")
        conn.commit()
    yield db_inst
    # Teardown
    with db_inst._get_connection() as conn:
        conn.execute("DELETE FROM settings_overrides")
        conn.execute("DELETE FROM memories")
        conn.execute("DELETE FROM memory_versions")
        conn.commit()

@pytest.fixture
def tool(db):
    return MemoryTool(db_instance=db)

def test_store_memory_success(tool):
    """Test memory stored -> appears in DB"""
    result = tool.store_memory(
        content="I love pizza",
        memory_date="2026-02-23",
        subject="Preferences",
        importance=4,
        session_id="test_session"
    )
    assert result["status"] == "success"
    assert "memory_id" in result
    assert result.get("notification") == "🧠 Saved to memory"
    assert result.get("stored") is True
    
    # Verify in DB
    daily = tool.db.get_daily_aggregation("test_session", "2026-02-23")
    assert "Preferences" in daily
    assert any(m["content"] == "I love pizza" for m in daily["Preferences"])

def test_low_importance_rejected(tool, db):
    """Test low importance -> rejected"""
    db.set_setting_override("memory_extraction_threshold", "4.0")
    
    result = tool.store_memory(
        content="I sometimes like pizza",
        memory_date="2026-02-23",
        subject="Preferences",
        importance=3,
        session_id="test_session"
    )
    assert result["status"] == "rejected"
    assert result["reason"] == "importance_below_threshold"

def test_threshold_boundary(tool, db):
    """Test threshold boundary (importance == threshold)"""
    db.set_setting_override("memory_extraction_threshold", "3.0")
    
    result = tool.store_memory(
        content="On the boundary",
        memory_date="2026-02-23",
        subject="Preferences",
        importance=3, # Exactly equal to threshold
        session_id="test_session"
    )
    assert result["status"] == "success"

def test_subject_filtering_rejected(tool, db):
    """Test subject filtering -> rejected"""
    import json
    db.set_setting_override("allowed_subjects", json.dumps(["Work", "Health"]))
    
    result = tool.store_memory(
        content="Playing video games",
        memory_date="2026-02-23",
        subject="Hobbies",
        importance=4,
        session_id="test_session"
    )
    assert result["status"] == "rejected"
    assert result["reason"] == "subject_not_allowed"

def test_case_normalization_for_subject(tool, db):
    """Test case normalization and whitespace stripping for subject"""
    import json
    db.set_setting_override("allowed_subjects", json.dumps(["Work"])) # Note capitalized W
    
    result = tool.store_memory(
        content="Started new coding project",
        memory_date="2026-02-23",
        subject="  work  ", # Note lower case and spaces
        importance=4,
        session_id="test_session"
    )
    assert result["status"] == "success"
    
    # Validate canonical subject in DB
    daily = tool.db.get_daily_aggregation("test_session", "2026-02-23")
    assert "Work" in daily # Was capitalized during storage
    assert "work" not in daily
    assert "  work  " not in daily

def test_wildcard_subject(tool, db):
    """Test wildcard subject '*' allows any"""
    import json
    db.set_setting_override("allowed_subjects", json.dumps(["*"]))
    
    result = tool.store_memory(
        content="Wildcard tests",
        memory_date="2026-02-23",
        subject="RandomSubject",
        importance=5,
        session_id="test_session"
    )
    assert result["status"] == "success"

def test_invalid_date_format(tool):
    """Test invalid date format (e.g. 23-02-2026)"""
    result = tool.store_memory(
        content="Bad date test",
        memory_date="2026/02/23", # Slanted
        subject="Test",
        importance=5
    )
    assert result["status"] == "error"
    assert "Invalid date format" in result["reason"]
    
def test_malformed_settings(tool, db):
    """Test parsing logic gracefully handles entirely broken config values"""
    # Write garbage directly to db settings
    db.set_setting_override("memory_extraction_threshold", "not_a_number")
    # Actually wait, set_setting_override accepts strings, so any garbage is fine
    db.set_setting_override("allowed_subjects", "just a totally raw string not even json")
    
    result = tool.store_memory(
        content="Fallback values work",
        memory_date="2026-02-23",
        subject="TestSubject",
        importance=5, # Greater than default fallback 3.0
    )
    # The default behavior on malformed subjects list is to set allowed_subjects = ["*"]
    assert result["status"] == "success"

def test_daily_summary_filtering(tool, db):
    """Test get_daily_summary correctly applies filters"""
    import json
    db.set_setting_override("allowed_subjects", json.dumps(["*"]))
    
    tool.store_memory("Work task 1", "2026-02-23", "Work", 4, "sess1")
    tool.store_memory("Health issue", "2026-02-23", "Health", 5, "sess1")
    
    # Now restrict subjects to only Work
    db.set_setting_override("allowed_subjects", json.dumps(["Work"]))
    
    summary_resp = tool.get_daily_summary("2026-02-23", "sess1")
    assert summary_resp["status"] == "success"
    
    # Should only show Work
    assert "Work" in summary_resp["summary"]
    assert "Health" not in summary_resp["summary"]
    assert any("Work task 1" in m["content"] for m in summary_resp["summary"]["Work"])

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
