from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union
import bcrypt
import jwt
from app.config import settings


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > 72:
        raise ValueError("Password must not exceed 72 bytes (bcrypt specification limit).")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        pw_bytes = plain_password.encode("utf-8")
        if len(pw_bytes) > 72:
            return False
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception:
        return False


def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict] = None
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token_with_error(token: str) -> tuple[Optional[dict], Optional[str]]:
    """
    Decode and validate a JWT access token, returning the payload and a distinct error reason.
    Returns (payload, None) on success, or (None, error_message) on failure.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        # Prevent token type confusion: invite tokens cannot be used as access tokens
        if payload.get("type") and payload.get("type") != "access":
            return None, "Invalid token type for API authentication"
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "Token has expired"
    except jwt.InvalidSignatureError:
        return None, "Invalid token signature"
    except jwt.PyJWTError:
        return None, "Invalid authentication token"
    except Exception:
        return None, "Invalid authentication token"


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token (backward-compatible)."""
    payload, _ = decode_access_token_with_error(token)
    return payload


def create_invite_token(
    organization_id: str,
    organization_name: str,
    email: Optional[str] = None,
    expires_in_days: int = 7
) -> str:
    """
    Create a cryptographically signed organization invite token.
    Prevents public tampering; payload is tied to the inviting organization.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=expires_in_days)
    payload = {
        "type": "org_invite",
        "org_id": organization_id,
        "org_name": organization_name,
        "email": email.lower() if email else None,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_invite_token(token: str) -> tuple[Optional[dict], Optional[str]]:
    """
    Validate and decode an organization invite token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "org_invite":
            return None, "Invalid invite token type"
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "Invitation link has expired. Please request a new invitation."
    except jwt.PyJWTError:
        return None, "Invalid or corrupted invitation link"
    except Exception:
        return None, "Invalid invitation link"

