"""Aggregates all `/api/v1` routes."""

from fastapi import APIRouter

from app.api.routes import datasets, generate, health, models, projects

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(projects.router)
api_v1_router.include_router(datasets.router)
api_v1_router.include_router(models.router)
api_v1_router.include_router(generate.router)
