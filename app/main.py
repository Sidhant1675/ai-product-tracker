"""
FastAPI application — main entry point.
Sets up the app, scheduler, static file serving, and lifespan management.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.database import create_tables
from app.api.routes import router as api_router
from app.scheduler.jobs import check_all_products

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# APScheduler instance
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown lifecycle."""
    # ── Startup ───────────────────────────────────────
    logger.info("🚀 Starting AI Limited Edition Product Tracker...")

    # Create database tables
    await create_tables()
    logger.info("✅ Database tables ready")

    # Start the scheduler
    scheduler.add_job(
        check_all_products,
        "interval",
        seconds=settings.scrape_interval_seconds,
        id="product_checker",
        name="Check All Products",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"⏱️  Scheduler started (interval: {settings.scrape_interval_seconds}s)"
    )

    if settings.telegram_configured:
        logger.info("📱 Telegram notifications enabled")
    else:
        logger.warning("📱 Telegram not configured — alerts will be logged only")

    logger.info("✅ Application ready! Visit http://localhost:8000")

    yield

    # ── Shutdown ──────────────────────────────────────
    scheduler.shutdown(wait=False)
    logger.info("👋 Scheduler stopped. Goodbye!")


# Create the FastAPI app
app = FastAPI(
    title="AI Limited Edition Product Tracker",
    description="Track limited-edition products and get instant alerts on stock & price changes.",
    version="1.0.0",
    lifespan=lifespan,
)

# Register API routes
app.include_router(api_router)

# Serve frontend static files
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the frontend dashboard."""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Frontend not found. API is running at /docs"}
