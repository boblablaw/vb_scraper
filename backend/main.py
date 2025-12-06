from __future__ import annotations

from fastapi import FastAPI

from backend.app.config import get_settings
from backend.app.routers import airports, conferences, health, players, scorecard, teams


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.api_title,
        description=settings.api_description,
        version=settings.api_version,
    )
    app.include_router(health.router)
    app.include_router(conferences.router)
    app.include_router(airports.router)
    app.include_router(teams.router)
    app.include_router(players.router)
    app.include_router(scorecard.router)
    return app


app = create_app()
