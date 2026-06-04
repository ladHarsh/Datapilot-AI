import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SessionService:
    """
    Manages user session lifecycle.
    In a full production environment, this would ideally be backed by Redis.
    For current implementation, tracks active sessions in memory/DB.
    """

    def __init__(self, db_session=None):
        self.db = db_session
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        self.session_expiry_minutes = 60

    def create_session(self, user_id: str, username: str, role: str) -> str:
        """Create a new session for an authenticated user."""
        session_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(minutes=self.session_expiry_minutes)
        
        session_data = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "is_active": True
        }
        
        self._active_sessions[session_id] = session_data
        logger.info(f"SessionService: created session '{session_id}' for user '{username}'.")
        return session_id

    def validate_session(self, session_id: str) -> bool:
        """Check if a session is valid and active."""
        session = self._active_sessions.get(session_id)
        if not session:
            logger.warning(f"SessionService: session '{session_id}' not found.")
            return False
            
        if not session.get("is_active"):
            logger.warning(f"SessionService: session '{session_id}' is inactive.")
            return False
            
        if datetime.utcnow() > session.get("expires_at"):
            logger.warning(f"SessionService: session '{session_id}' has expired.")
            self.invalidate_session(session_id)
            return False
            
        return True

    def get_session_user(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user details for a valid session."""
        if self.validate_session(session_id):
            return self._active_sessions.get(session_id)
        return None

    def invalidate_session(self, session_id: str) -> None:
        """Invalidate a session on logout or expiration."""
        if session_id in self._active_sessions:
            self._active_sessions[session_id]["is_active"] = False
            logger.info(f"SessionService: session '{session_id}' invalidated.")

    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions from tracking."""
        now = datetime.utcnow()
        expired_keys = [
            sid for sid, data in self._active_sessions.items() 
            if now > data["expires_at"] or not data["is_active"]
        ]
        
        for sid in expired_keys:
            del self._active_sessions[sid]
            
        logger.info(f"SessionService: cleaned up {len(expired_keys)} expired sessions.")
        return len(expired_keys)
