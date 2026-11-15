from typing import Any, Optional
from pydantic import BaseModel


class ApiResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None
    error: Optional[Any] = None


def success_response(data: Any = None, message: Optional[str] = None) -> dict:
    return {
        "success": True,
        "message": message,
        "data": data,
        "error": None
    }


def error_response(message: str, error_details: Any = None) -> dict:
    return {
        "success": False,
        "message": message,
        "data": None,
        "error": error_details
    }
