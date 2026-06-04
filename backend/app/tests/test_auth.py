import pytest
from app.services.auth.auth_service import AuthService
from app.services.auth.jwt_service import JWTService
from app.services.auth.session_service import SessionService

def test_session_lifecycle():
    service = SessionService()
    user_id = "123"
    username = "testuser"
    role = "analyst"
    
    # 1. Create
    session_id = service.create_session(user_id, username, role)
    assert session_id is not None
    
    # 2. Validate
    assert service.validate_session(session_id) is True
    
    # 3. Get User
    user = service.get_session_user(session_id)
    assert user["user_id"] == user_id
    assert user["username"] == username
    
    # 4. Invalidate
    service.invalidate_session(session_id)
    assert service.validate_session(session_id) is False

def test_jwt_generation_and_validation():
    service = JWTService(secret_key="test_secret_key_long_enough_for_hs256")
    data = {"sub": "123", "sid": "session_abc", "role": "admin"}
    
    token = service.create_access_token(data)
    assert token is not None
    
    payload = service.validate_token(token)
    assert payload["sub"] == "123"
    assert payload["sid"] == "session_abc"
    assert payload["type"] == "access"

def test_jwt_invalid_type():
    service = JWTService(secret_key="test_secret_key_long_enough_for_hs256")
    data = {"sub": "123", "sid": "session_abc"}
    
    token = service.create_refresh_token(data)
    
    with pytest.raises(Exception) as exc:
        service.validate_token(token, expected_type="access")
    assert "Invalid token type" in str(exc.value)
