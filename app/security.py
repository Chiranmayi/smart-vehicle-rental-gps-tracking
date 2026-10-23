
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.config import settings

password_hash = PasswordHash.recommended()

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Convert a plain-text password into a secure hash."""
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Check a password against its stored hash."""
    return password_hash.verify(password, hashed)


def create_access_token(user_id: int, role: str) -> str:
    """Create a signed JWT token for an authenticated user."""
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )

    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )
