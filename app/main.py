import asyncio

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import init_db
from app.webhook.router import router as webhook_router

logger = get_logger(__name__)


def create_app() -> FastAPI:
    from contextlib import asynccontextmanager
    from pathlib import Path
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    from app.api.admin import router as admin_router

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await init_db()
        logger.info("app_started")
        yield

    app = FastAPI(
        title="LevelOne Voice Agent",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["POST", "GET", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(webhook_router)
    app.include_router(admin_router)

    # Serve dashboard
    dashboard_dir = Path(__file__).parent / "dashboard"
    if dashboard_dir.exists():
        app.mount("/dashboard/static", StaticFiles(directory=str(dashboard_dir)), name="dashboard-static")

        @app.get("/dashboard", include_in_schema=False)
        async def serve_dashboard():
            return FileResponse(str(dashboard_dir / "index.html"))

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "voice-agent"}

    return app



def main() -> None:
    configure_logging()
    settings = get_settings()
    app = create_app()
    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
        log_config=None,  # structlog handles logging
    )


if __name__ == "__main__":
    main()
