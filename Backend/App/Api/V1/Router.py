"""Version 1 API router: every /api/v1 route module is included here."""

from fastapi import APIRouter

from Backend.App.Api.V1 import Analysis, Cases, Evidence, Health, Jobs, Notifications, Realtime, Search, System

api_router = APIRouter()
api_router.include_router(Health.router)
api_router.include_router(System.router)
api_router.include_router(Cases.router)
api_router.include_router(Evidence.router)
api_router.include_router(Search.router)
api_router.include_router(Jobs.router)
api_router.include_router(Analysis.router)
api_router.include_router(Notifications.router)
api_router.include_router(Realtime.router)
