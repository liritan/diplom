from fastapi import APIRouter
from app.api.endpoints import auth, tests, profiles, chat, analysis, plans, admin

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(tests.router, prefix="/tests", tags=["tests"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(plans.router, prefix="/plans", tags=["plans"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])


