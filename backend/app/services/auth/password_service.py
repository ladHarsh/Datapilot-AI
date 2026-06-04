"""
Password Service
================
Handles bcrypt password hashing and verification.
Prevents plaintext password storage.
"""

import logging
import re
import secrets
import string
from typing import Tuple

import bcrypt

logger = logging.getLogger(__name__)

# ─── Password policy ──────────────────────────────────────────────────────────
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
BCRYPT_ROUNDS = 12      # Work factor — increase for stronger security (increases hash time)


class WeakPasswordError(Exception):
    """Raised when a password does not meet policy requirements."""
    pass


class PasswordService:
    """
    Provides bcrypt-based password hashing, verification, and policy enforcement.

    Security principles:
    - Never store or log plaintext passwords.
    - Use bcrypt with configurable work factor (default: 12 rounds).
    - Enforce minimum password complexity.
    - Use constant-time comparison to prevent timing attacks.
    """

    def __init__(self, rounds: int = BCRYPT_ROUNDS):
        self.rounds = rounds
        logger.info("PasswordService: initialized (bcrypt rounds=%d).", rounds)

    # ── Public API ────────────────────────────────────────────────────────────

    def hash_password(self, plaintext: str) -> str:
        """
        Hash a plaintext password using bcrypt.

        Args:
            plaintext: The raw password string.

        Returns:
            bcrypt hash string (safe to store in database).

        Raises:
            WeakPasswordError: If password does not meet policy.
            ValueError:        If plaintext is empty.
        """
        if not plaintext:
            raise ValueError("Password cannot be empty.")

        # Policy check before hashing
        self.validate_password_policy(plaintext)

        hashed = bcrypt.hashpw(
            plaintext.encode("utf-8"),
            bcrypt.gensalt(rounds=self.rounds),
        )
        logger.debug("PasswordService: password hashed successfully.")
        return hashed.decode("utf-8")

    def verify(self, plaintext: str, hashed: str) -> bool:
        """
        Verify a plaintext password against a stored bcrypt hash.
        Uses constant-time comparison to prevent timing attacks.

        Args:
            plaintext: The raw password attempt.
            hashed:    The stored bcrypt hash from the database.

        Returns:
            True if password matches, False otherwise.
        """
        if not plaintext or not hashed:
            logger.warning("PasswordService: empty plaintext or hash during verify.")
            return False

        try:
            result = bcrypt.checkpw(
                plaintext.encode("utf-8"),
                hashed.encode("utf-8"),
            )
            logger.debug("PasswordService: password verification result=%s.", result)
            return result
        except Exception as exc:
            logger.error("PasswordService: verification error — %s", exc)
            return False

    def validate_password_policy(self, password: str) -> None:
        """
        Enforce password complexity policy.

        Requirements:
        - Minimum 8 characters
        - Maximum 128 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character

        Raises:
            WeakPasswordError: If any requirement is not met.
        """
        errors = []

        if len(password) < MIN_PASSWORD_LENGTH:
            errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")

        if len(password) > MAX_PASSWORD_LENGTH:
            errors.append(f"Password must not exceed {MAX_PASSWORD_LENGTH} characters.")

        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter.")

        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter.")

        if not re.search(r"\d", password):
            errors.append("Password must contain at least one digit.")

        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?`~]", password):
            errors.append("Password must contain at least one special character.")

        if errors:
            raise WeakPasswordError(
                "Password does not meet security requirements: " + " | ".join(errors)
            )

        logger.debug("PasswordService: password passed policy validation.")

    def generate_secure_password(self, length: int = 16) -> str:
        """
        Generate a cryptographically secure random password.

        Args:
            length: Desired password length (minimum 12).

        Returns:
            A secure random password string.
        """
        length = max(length, 12)
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{}|;:,.<>?"

        while True:
            password = "".join(secrets.choice(alphabet) for _ in range(length))
            try:
                self.validate_password_policy(password)
                return password
            except WeakPasswordError:
                continue   # Retry if generated password doesn't meet policy by chance

    def needs_rehash(self, hashed: str) -> bool:
        """
        Check if a stored hash was created with fewer rounds than current config.
        Use this to upgrade hashes after increasing the work factor.

        Args:
            hashed: Stored bcrypt hash.

        Returns:
            True if the hash should be rehashed (work factor too low).
        """
        try:
            current_rounds = bcrypt.gensalt(rounds=self.rounds)
            stored_rounds = int(hashed.split("$")[2])
            needs_upgrade = stored_rounds < self.rounds
            if needs_upgrade:
                logger.info(
                    "PasswordService: hash uses %d rounds, current is %d — rehash recommended.",
                    stored_rounds, self.rounds,
                )
            return needs_upgrade
        except Exception:
            return False
