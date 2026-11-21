import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db, check_db_health, engine
from app.config import settings

logger = logging.getLogger("brandproof.health")
router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint verifying API service and database connectivity.
    Ensures no internal credentials or connection strings are leaked in error responses.
    """
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Health check database connectivity failure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "degraded",
                "database": "unreachable",
                "version": settings.VERSION,
            }
        )

    dialect_name = engine.dialect.name
    res = {
        "status": "healthy",
        "database": db_status,
        "database_dialect": dialect_name,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }
    if settings.ENVIRONMENT.lower() == "preview":
        res["storage"] = "ephemeral-local"
        res["warning"] = (
            "PREVIEW MODE: Database (SQLite) and local uploads under /tmp are ephemeral. "
            "Data resets when Render Free instance spins down due to inactivity."
        )
    return res


@router.get("/health/db")
def database_health_check():
    """
    Detailed database health check verifying connection pool health and vitality
    without exposing connection strings, hosts, credentials, or sensitive configuration.
    """
    health = check_db_health()
    if not health.get("connected", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "database": "unreachable",
                "error": health.get("error", "Database connection check failed"),
            }
        )
    return health
