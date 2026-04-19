"""FastAPI application entrypoint for the StratForge SaaS wrapper."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.database import create_tables
from api.routers import auth, billing, chart, library, projects, provider, runs, strategies, trades


logger = logging.getLogger("stratforge.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await create_tables()
    logger.info("=" * 60)
    logger.info("StratForge API ready")
    logger.info("API base: http://127.0.0.1:8000")
    logger.info("API docs: http://127.0.0.1:8000/docs")
    logger.info("Health: http://127.0.0.1:8000/health")
    logger.info("Expected frontend: %s", settings.frontend_url)
    logger.info("=" * 60)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Multi-user API for projects, strategies, runs, chart data, and billing.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(strategies.router)
app.include_router(runs.router)
app.include_router(chart.router)
app.include_router(trades.router)
app.include_router(library.router)
app.include_router(provider.router)
app.include_router(billing.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}
