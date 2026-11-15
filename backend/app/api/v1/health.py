import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
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

    return {
        "status": "healthy",
        "database": db_status,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }
