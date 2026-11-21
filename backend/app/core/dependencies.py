from typing import Generator, List, Optional
from fastapi import Depends, HTTPException, Request, UploadFile, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import SessionLocal, get_db
from app.core.security import decode_access_token, decode_access_token_with_error
from app.models.user import User, UserRole

security_scheme = HTTPBearer(auto_error=False)

DEFAULT_MAX_UPLOAD_SIZE = 15 * 1024 * 1024  # 15 MB


async def read_upload_file_bounded(file: UploadFile, max_bytes: int = DEFAULT_MAX_UPLOAD_SIZE) -> bytes:
    """
    Reads an UploadFile in bounded chunks to protect against memory exhaustion attacks.
    Aborts immediately and raises 413 if the payload exceeds max_bytes.
    """
    chunk_size = 64 * 1024  # 64 KB chunks
    total_bytes = 0
    buffer = bytearray()
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            max_mb = max_bytes // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Uploaded file exceeds maximum allowed limit of {max_mb} MB.",
            )
        buffer.extend(chunk)
    return bytes(buffer)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    raw_token = None
    if credentials and credentials.credentials:
        raw_token = credentials.credentials
    elif request and "brandproof_token" in request.cookies:
        raw_token = request.cookies.get("brandproof_token")

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload, error_reason = decode_access_token_with_error(raw_token)
    if not payload:
        error_detail = error_reason or "Invalid or expired authentication token"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_detail,
            headers={"WWW-Authenticate": f'Bearer error="invalid_token", error_description="{error_detail}"'},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


def require_roles(allowed_roles: List[UserRole]):
    """Role-Based Access Control (RBAC) dependency factory."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        allowed_values = [r.value if isinstance(r, UserRole) else str(r) for r in allowed_roles]
        if current_user.role not in allowed_values and current_user.role != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Role '{current_user.role}' lacks permission for this action. Required: {allowed_values}",
            )
        return current_user
    return role_checker
