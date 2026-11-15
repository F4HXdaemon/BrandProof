from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any
from app.config import settings
from seed import seed_database

router = APIRouter(prefix="/demo", tags=["Demo Mode"])


@router.post("/reset", response_model=Dict[str, Any])
def reset_demo_state():
    """
    Development/Demo only utility.
    Resets and reseeds ONLY the Northstar Cloud demonstration organization.
    Strictly forbidden in production environments.
    """
    if settings.ENVIRONMENT.lower() in ("production", "preview") or not settings.ENABLE_DEMO_RESET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo reset is disabled in production and preview environments."
        )

    try:
        seed_database()
        return {
            "status": "success",
            "message": "BrandProof demo organization 'Northstar Cloud' successfully reset to pristine state.",
            "personas": [
                {"role": "Admin", "name": "Alexandra Vance", "email": "admin@northstarcloud.com"},
                {"role": "Brand Manager", "name": "Marcus Sterling", "email": "brandmanager@northstarcloud.com"},
                {"role": "Fact Owner", "name": "Elena Rostova", "email": "factowner@northstarcloud.com"},
                {"role": "Reviewer", "name": "Julian Chen", "email": "reviewer@northstarcloud.com"},
                {"role": "Creator", "name": "Samantha Reed", "email": "creator@northstarcloud.com"},
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset demo database: {str(e)}"
        )
