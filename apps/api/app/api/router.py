"""Aggregates all `/api/v1` routes."""

from fastapi import APIRouter

from app.api.routes import health, projects

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(projects.router)
