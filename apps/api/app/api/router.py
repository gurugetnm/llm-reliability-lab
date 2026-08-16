"""Aggregates all `/api/v1` routes."""

from fastapi import APIRouter

from app.api.routes import datasets, experiments, generate, health, models, projects, runs

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(projects.router)
api_v1_router.include_router(datasets.router)
api_v1_router.include_router(experiments.router)
api_v1_router.include_router(runs.experiment_runs_router)
api_v1_router.include_router(runs.runs_router)
api_v1_router.include_router(models.router)
api_v1_router.include_router(generate.router)
