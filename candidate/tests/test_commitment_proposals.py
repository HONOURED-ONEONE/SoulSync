from soulsync.services.commitment_proposals import new_blank_proposal, normalize_proposal

def test_blank_proposal_shape_and_unique_ids():
    a, b = new_blank_proposal(), new_blank_proposal()
    assert a["proposal_id"] != b["proposal_id"]
    assert a["status"] == "draft"
    assert a["title"] is None and a["category"] is None
    assert a["field_sources"] == {} and a["missing_fields"] == []

def test_normalize_strips_and_rejects_unknowns_without_mutation():
    source = {"title": "  Pay fee  ", "category": "FINANCE", "estimated_minutes": "15", "reminder_minutes_before": "0", "unexpected": "drop"}
    result = normalize_proposal(source)
    assert result["title"] == "Pay fee"
    assert result["category"] == "finance"
    assert result["estimated_minutes"] == 15
    assert result["reminder_minutes_before"] == 0
    assert "unexpected" not in result
    assert source["title"] == "  Pay fee  "

def test_normalize_invalid_values_are_none():
    result = normalize_proposal({"category": "invented", "estimated_minutes": 0, "reminder_minutes_before": -1, "title": "  "})
    assert result["category"] is None
    assert result["estimated_minutes"] is None
    assert result["reminder_minutes_before"] is None
    assert result["title"] is None
