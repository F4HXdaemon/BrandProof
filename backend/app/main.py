import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.config import settings
from app.database import engine, Base
from app.api.v1.router import api_router

logger = logging.getLogger("brandproof.main")

# Ensure all models are loaded
import app.models  # noqa: F401

# In PREVIEW and development SQLite modes, safely initialize database tables
# and storage directories upon application startup.
# In PRODUCTION mode, Alembic migrations ('alembic upgrade head') are strictly authoritative.
env = settings.ENVIRONMENT.lower()
is_testing = "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules
if not is_testing and env in ("preview", "development") and settings.DATABASE_URL.startswith("sqlite"):
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    logger.info(f"[{env.upper()} MODE] SQLite database & storage directory safely initialized.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
# BrandProof Governance API
**"Every claim, traced to its source."**

AI proposes. Evidence decides. People approve.
NO VALID SOURCE = NO FINDING. AI must never be the final approver.
    """,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sanitize_validation_errors(errors: list) -> list:
    """
    Sanitize Pydantic validation errors by stripping raw input values.
    Prevents credentials, passwords, tokens, and sensitive private user data
    from ever being echoed back in 422 Unprocessable Entity responses.
    """
    sanitized = []
    for err in errors:
        cleaned = {
            "type": err.get("type", "value_error"),
            "loc": err.get("loc", []),
            "msg": err.get("msg", "Invalid value"),
        }
        sanitized.append(cleaned)
    return sanitized


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    sanitized_errors = _sanitize_validation_errors(exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Validation error in submitted payload",
            "error": sanitized_errors,
            "detail": sanitized_errors,
        },
    )


@app.get("/")
def root():
    resp = {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "operational",
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs",
        "philosophy": "AI proposes. Evidence decides. People approve.",
        "invariant": "NO VALID SOURCE = NO FINDING",
    }
    if settings.ENVIRONMENT.lower() == "preview":
        resp["preview_notice"] = (
            "PREVIEW DEPLOYMENT: Running on ephemeral SQLite (/tmp/brandproof-preview.db) "
            "and local file storage (/tmp/brandproof-uploads). Database and uploaded files "
            "reset upon service restart. For persistent data, deploy in production mode with PostgreSQL and S3."
        )
    return resp


# Include API v1 routes
app.include_router(api_router, prefix=settings.API_V1_STR)
