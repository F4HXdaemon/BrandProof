import re
import time
from collections import defaultdict
from threading import Lock
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import verify_password, hash_password, create_access_token
from app.core.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.schemas.auth_and_user import LoginRequest, TokenResponse, RegisterRequest, UserOut
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/auth", tags=["Authentication"])


class RateLimiter:
    """
    Sliding window rate limiter for authentication brute-force protection.
    Tracks failed attempts by client IP and account email.
    """
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts: dict[str, list[float]] = defaultdict(list)
        self.lock = Lock()

    def check(self, key: str) -> None:
        now = time.time()
        with self.lock:
            self.attempts[key] = [t for t in self.attempts[key] if now - t < self.window_seconds]
            if len(self.attempts[key]) >= self.max_attempts:
                oldest = self.attempts[key][0]
                retry_after = int(self.window_seconds - (now - oldest)) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed login attempts. Please try again in {retry_after} seconds.",
                    headers={"Retry-After": str(max(retry_after, 1))},
                )

    def record_failure(self, key: str) -> None:
        with self.lock:
            self.attempts[key].append(time.time())

    def reset(self, key: str) -> None:
        with self.lock:
            if key in self.attempts:
                del self.attempts[key]


login_limiter = RateLimiter(max_attempts=5, window_seconds=300)


def _slugify(text: str) -> str:
    """Generate a clean URL-safe slug from text."""
    slug = re.sub(r"[^\w\s-]", "", text.strip().lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug or "org"


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, http_req: Request, db: Session = Depends(get_db)):
    """Authenticate a user and return a JWT access token with brute-force rate limiting."""
    client_ip = http_req.client.host if http_req.client else "unknown"
    rate_key = f"{client_ip}:{request.email.lower()}"
    login_limiter.check(rate_key)

    user = db.query(User).filter(User.email == request.email.lower()).first()
    if not user or not verify_password(request.password, user.hashed_password):
        login_limiter.record_failure(rate_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Reset failed attempts upon successful login
    login_limiter.reset(rate_key)

    access_token = create_access_token(
        subject=user.id,
        extra_claims={
            "role": user.role,
            "org_id": user.organization_id,
            "email": user.email,
        }
    )

    record_audit_event(
        db=db,
        organization_id=user.organization_id,
        actor_id=user.id,
        action="USER_LOGIN",
        entity_type="User",
        entity_id=user.id,
        metadata={"email": user.email, "role": user.role}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user)
    )


@router.post("/register", response_model=TokenResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new organization and founding admin user.
    Security Invariant: A registrant can NEVER join or take over an existing organization
    through public registration. Existing organization membership requires an authenticated
    invitation or administrator action.
    """
    # 1. Enforce password complexity
    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )
    if len(request.password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must not exceed 72 bytes.",
        )

    # 2. Check if user email already exists
    existing_user = db.query(User).filter(User.email == request.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # 3. Validate & sanitize organization name
    org_name = request.organization_name.strip()
    if len(org_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization name must be at least 2 characters long.",
        )

    base_slug = _slugify(request.organization_slug or org_name)
    if len(base_slug) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid organization slug.",
        )

    # 4. Strictly prevent organization collision / takeover
    existing_org = db.query(Organization).filter(Organization.slug == base_slug).first()
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this slug already exists. Please choose a unique organization name.",
        )

    # 5. Extract domain
    email_domain = request.email.split("@")[-1].lower() if "@" in request.email else None

    # 6. Create new Organization and Admin atomically
    org = Organization(
        name=org_name,
        slug=base_slug,
        domain=email_domain,
        is_active=True,
    )
    db.add(org)
    db.flush()

    user = User(
        organization_id=org.id,
        email=request.email.lower(),
        hashed_password=hash_password(request.password),
        full_name=request.full_name.strip(),
        role=UserRole.ADMIN.value,
        title="Organization Owner",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(
        subject=user.id,
        extra_claims={
            "role": user.role,
            "org_id": user.organization_id,
            "email": user.email,
        }
    )

    record_audit_event(
        db=db,
        organization_id=org.id,
        actor_id=user.id,
        action="ORGANIZATION_INITIALIZED",
        entity_type="Organization",
        entity_id=org.id,
        metadata={"name": org.name, "admin": user.email}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user)
    )


@router.get("/me", response_model=UserOut)
def get_current_authenticated_user(current_user: User = Depends(get_current_user)):
    """Retrieve profile of currently authenticated user."""
    return UserOut.model_validate(current_user)
