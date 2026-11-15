from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.config import settings
from app.database import engine, Base
from app.api.v1.router import api_router

# Ensure all models are loaded
import app.models  # noqa: F401

# In development SQLite mode, allow automatic table creation for zero-setup local runs;
# in production, Alembic migrations ('alembic upgrade head') are strictly authoritative.
if settings.ENVIRONMENT.lower() == "development" and settings.DATABASE_URL.startswith("sqlite"):
    Base.metadata.create_all(bind=engine)

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
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "operational",
        "docs_url": "/docs",
        "philosophy": "AI proposes. Evidence decides. People approve.",
        "invariant": "NO VALID SOURCE = NO FINDING",
    }


# Include API v1 routes
app.include_router(api_router, prefix=settings.API_V1_STR)
