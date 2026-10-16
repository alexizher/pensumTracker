from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import DEFAULT_ORIGINS, Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from routers.academic_router import router


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    settings = settings or get_settings()

    app = FastAPI(title="Pensum Tracker API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[*DEFAULT_ORIGINS, *settings.allowed_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
