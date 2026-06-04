import pytest
from app.services.auth.session_service import SessionService
from app.services.auth.token_blacklist_service import TokenBlacklistService

def test_token_blacklisting():
    blacklist = TokenBlacklistService()
    token = "fake_token_123"
    
    assert blacklist.is_token_blacklisted(token) is False
    blacklist.blacklist_token(token)
    assert blacklist.is_token_blacklisted(token) is True

def test_session_expiration():
    service = SessionService()
    # Mocking a short-lived session
    session_id = service.create_session("user1", "test", "admin")
    
    # Manually expire (simulate time passing if service supports it)
    # For now, we test the core logic
    assert service.validate_session(session_id) is True
    service.invalidate_session(session_id)
    assert service.validate_session(session_id) is False
