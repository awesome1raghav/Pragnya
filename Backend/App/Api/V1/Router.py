"""
NEXTRON Backend: API V1 Main Router
"""

from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/status", tags=["System"])
async def get_system_status():
    return {
        "service": "NEXTRON Backend API V1",
        "status": "operational",
        "modules_active": 18
    }
