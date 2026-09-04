"""FastAPI application setup, router configuration, middleware, and exception handlers."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.domain.exceptions import DomainException
from src.infrastructure.config.settings import get_settings
from src.presentation.api.routes import pipeline_router

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    """Data model for health check status endpoint response."""

    status: str
    environment: str
    version: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager handling application startup and shutdown events."""
    settings = get_settings()
    logger.info(
        "Starting Marketing Automation API service in %s environment",
        settings.environment,
    )
    yield
    logger.info("Shutting down Marketing Automation API service")


def create_app() -> FastAPI:
    """Factory function creating configured FastAPI application instance."""
    app = FastAPI(
        title="Marketing Automation Pipeline API",
        version="0.1.0",
        description="API for ad data normalization, anomaly detection, and briefing generation.",
        lifespan=lifespan,
    )

    # Configure CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount Route Handlers
    app.include_router(pipeline_router)

    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    def health_check() -> HealthResponse:
        """Health check endpoint returning service status and active environment."""
        settings = get_settings()
        return HealthResponse(
            status="healthy",
            environment=settings.environment,
            version="0.1.0",
        )

    # -------------------------------------------------------------------------
    # Exception Handlers
    # -------------------------------------------------------------------------
    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
        """Translates custom domain exceptions to HTTP 400 Bad Request responses."""
        logger.warning("Domain exception encountered on %s: %s", request.url.path, str(exc))
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "error_type": exc.__class__.__name__},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Translates ValueError validation errors to HTTP 400 Bad Request responses."""
        logger.warning("Validation error encountered on %s: %s", request.url.path, str(exc))
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "error_type": "ValueError"},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Translates uncaught infrastructure/runtime errors to HTTP 500 responses."""
        logger.error(
            "Unhandled exception encountered on %s: %s",
            request.url.path,
            str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error occurred during processing."},
        )

    return app


app = create_app()
