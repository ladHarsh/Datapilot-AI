"""
Authentication Service
=======================
Handles login credential validation, user lookup, and authentication workflow.
Integrates with JWT service and RBAC system.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class UserNotFoundError(AuthenticationError):
    """Raised when user does not exist."""
    pass


class InvalidCredentialsError(AuthenticationError):
    """Raised when password does not match."""
    pass


class AccountLockedError(AuthenticationError):
    """Raised when account has been locked due to failed attempts."""
    pass


class AuthService:
    """
    Handles the full authentication workflow:
    1. Look up user by username/email
    2. Verify password hash
    3. Check account status (active/locked)
    4. Issue JWT access + refresh tokens
    5. Log authentication events
    """

    MAX_FAILED_ATTEMPTS = 5

    def __init__(self, db: Session, jwt_service=None, password_service=None, session_service=None):
        from app.services.auth.jwt_service import JWTService
        from app.services.auth.password_service import PasswordService
        from app.services.auth.session_service import SessionService

        self.db = db
        self.jwt_service = jwt_service or JWTService()
        self.password_service = password_service or PasswordService()
        self.session_service = session_service or SessionService(db)

    # ── Public API ────────────────────────────────────────────────────────────

    def login(self, username: str, password: str, client_ip: str = "unknown") -> Dict[str, Any]:
        """
        Authenticate a user and return JWT tokens.

        Args:
            username:   Username or email address.
            password:   Plaintext password (will be verified against hash).
            client_ip:  Client IP for audit logging.

        Returns:
            dict with access_token, refresh_token, token_type, expires_in, user_info.

        Raises:
            UserNotFoundError:       If user does not exist.
            InvalidCredentialsError: If password is wrong.
            AccountLockedError:      If account is locked.
        """
        logger.info("AuthService: login attempt for user='%s' from ip='%s'.", username, client_ip)

        # 1. Look up user
        user = self._get_user(username)
        if user is None:
            logger.warning("AuthService: user not found — '%s'.", username)
            # Use same error to prevent username enumeration
            raise InvalidCredentialsError("Invalid username or password.")

        # 2. Check account lock
        if user.get("is_locked", False):
            logger.warning("AuthService: account locked — '%s'.", username)
            raise AccountLockedError("Account is locked. Contact an administrator.")

        # 3. Verify password
        if not self.password_service.verify(password, user["hashed_password"]):
            logger.warning("AuthService: invalid password for user='%s'.", username)
            self._record_failed_attempt(user["id"])
            raise InvalidCredentialsError("Invalid username or password.")

        # 4. Reset failed attempts on success
        self._reset_failed_attempts(user["id"])

        # 5. Create Session
        session_id = self.session_service.create_session(
            user_id=str(user["id"]),
            username=user["username"],
            role=user["role"]
        )

        # 6. Generate tokens
        token_data = {
            "sub": str(user["id"]),
            "username": user["username"],
            "role": user["role"],
            "email": user.get("email", ""),
            "sid": session_id,
        }
        access_token = self.jwt_service.create_access_token(token_data)
        refresh_token = self.jwt_service.create_refresh_token({"sub": str(user["id"]), "sid": session_id})

        logger.info("AuthService: login successful for user='%s' role='%s' session='%s'.", username, user["role"], session_id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "session_id": session_id,
            "token_type": "bearer",
            "expires_in": self.jwt_service.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user_info": {
                "id": user["id"],
                "username": user["username"],
                "email": user.get("email", ""),
                "role": user["role"],
                "last_login": datetime.utcnow().isoformat(),
            },
        }

    def refresh_tokens(self, refresh_token: str) -> Dict[str, Any]:
        """
        Issue a new access token given a valid refresh token.

        Args:
            refresh_token: The refresh JWT token string.

        Returns:
            dict with new access_token and token metadata.
        """
        payload = self.jwt_service.validate_token(refresh_token)
        user_id = payload.get("sub")

        user = self._get_user_by_id(user_id)
        if user is None:
            raise AuthenticationError("User not found during token refresh.")

        token_data = {
            "sub": str(user["id"]),
            "username": user["username"],
            "role": user["role"],
        }
        new_access_token = self.jwt_service.create_access_token(token_data)
        logger.info("AuthService: tokens refreshed for user_id='%s'.", user_id)

        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": self.jwt_service.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    def logout(self, token: str) -> Dict[str, str]:
        """
        Invalidate a JWT token and its associated session.

        Args:
            token: The access token to invalidate.

        Returns:
            dict with logout confirmation.
        """
        try:
            payload = self.jwt_service.validate_token(token)
            session_id = payload.get("sid")
            if session_id:
                self.session_service.invalidate_session(session_id)
                logger.info("AuthService: session '%s' invalidated during logout.", session_id)
        except Exception as exc:
            logger.warning("AuthService: logout token validation failed (token may be expired) — %s", exc)

        # Still return success for logout
        return {"message": "Successfully logged out."}

    def validate_request_token(self, token: str) -> Dict[str, Any]:
        """
        Validate an incoming request's Bearer token and session integrity.
        Used by FastAPI dependency injection.
        """
        payload = self.jwt_service.validate_token(token)
        session_id = payload.get("sid")
        
        if not session_id or not self.session_service.validate_session(session_id):
            logger.warning("AuthService: invalid or expired session for sub='%s'.", payload.get("sub"))
            raise AuthenticationError("Session expired or invalid. Please login again.")

        logger.debug("AuthService: token and session validated for sub='%s'.", payload.get("sub"))
        return payload

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_user(self, username: str) -> Optional[Dict]:
        """Fetch user by username or email from the database."""
        try:
            from app.db.models.user_model import User
            user = (
                self.db.query(User)
                .filter(
                    (User.username == username) | (User.email == username)
                )
                .first()
            )
            if user:
                return {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "hashed_password": user.hashed_password,
                    "is_locked": user.is_locked,
                    "failed_attempts": user.failed_login_attempts,
                }
        except Exception as exc:
            logger.error("AuthService: DB error fetching user — %s", exc)
        return None

    def _get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Fetch user by primary key."""
        try:
            from app.db.models.user_model import User
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                return {"id": user.id, "username": user.username, "role": user.role}
        except Exception as exc:
            logger.error("AuthService: DB error fetching user by id — %s", exc)
        return None

    def _record_failed_attempt(self, user_id: int) -> None:
        """Increment failed login attempts and lock account if threshold reached."""
        try:
            from app.db.models.user_model import User
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
                    user.is_locked = True
                    logger.warning("AuthService: account locked due to failed attempts — user_id=%d.", user_id)
                self.db.commit()
        except Exception as exc:
            logger.error("AuthService: failed to record attempt — %s", exc)
            self.db.rollback()

    def _reset_failed_attempts(self, user_id: int) -> None:
        """Reset failed login counter after successful login."""
        try:
            from app.db.models.user_model import User
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                user.failed_login_attempts = 0
                self.db.commit()
        except Exception as exc:
            logger.error("AuthService: failed to reset attempts — %s", exc)
            self.db.rollback()

    def register_user(self, user_in) -> Any:
        """Register a new user in the system."""
        from app.db.models.user_model import User
        hashed_password = self.password_service.hash_password(user_in.password)
        db_user = User(
            username=user_in.username,
            email=user_in.email,
            hashed_password=hashed_password,
            role="user",
            is_active=True
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        logger.info("AuthService: user registered successfully — '%s'.", user_in.username)
        return db_user

# ── Standalone Wrapper Functions for FastAPI Routes ───────────────────────────

def authenticate_user(db: Session, username: str, password: str) -> Any:
    """Wrapper for AuthService.login compatibility."""
    auth_service = AuthService(db)
    try:
        result = auth_service.login(username, password)
        # Return the user model instance for compatibility
        from app.db.models.user_model import User
        return db.query(User).filter(User.id == result["user_info"]["id"]).first()
    except Exception:
        return None

def create_access_token(data: dict) -> str:
    """Wrapper for JWTService compatibility."""
    from app.services.auth.jwt_service import JWTService
    jwt_service = JWTService()
    return jwt_service.create_access_token(data)

def register_user(db: Session, user_in) -> Any:
    """Wrapper for AuthService.register_user compatibility."""
    auth_service = AuthService(db)
    return auth_service.register_user(user_in)
