import pytest
from soulsync.services.voice import get_fallback_response

def test_fallback_response_modes():
    modes = ["Cheer me on", "Help me plan", "Reflect with me", "Study buddy"]
    for mode in modes:
        response = get_fallback_response(mode)
        assert isinstance(response, str)
        assert len(response) > 0
        assert "AI features are in fallback mode" in response or mode in response.lower()

def test_fallback_response_unknown_mode():
    response = get_fallback_response("Unknown Mode")
    assert isinstance(response, str)
    assert len(response) > 0
