"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import cmdb, health, itsm, satellite, sccm, squad1, tenable
from app.core.config import get_settings


settings = get_settings()

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info("Starting %s", settings.app_name)

    yield

    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description=(
        "VPM360 integration API for vulnerability, CMDB, "
        "ITSM, and Satellite workflows."
    ),
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
)


# Configure allowed frontend origins before production deployment.
# Avoid wildcard origins when credentials are enabled.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.cors_allowed_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


for router in (
    health.router,
    tenable.router,
    cmdb.router,
    itsm.router,
    satellite.router,
    squad1.router,
    sccm.router,
):
    app.include_router(
        router,
        prefix=settings.api_v1_prefix,
    )

# Include istm alias without duplicating routes in OpenAPI docs
app.include_router(
    itsm.istm_router,
    prefix=settings.api_v1_prefix,
    include_in_schema=False,
)



@app.get("/", tags=["System"])
def root() -> dict[str, str]:
    """Return basic API information."""
    return {
        "name": settings.app_name,
        "status": "running",
        "docs": f"{settings.api_v1_prefix}/../docs",
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    _,
    exc: Exception,
) -> JSONResponse:
    """Log unexpected errors without exposing internal details."""
    logger.exception(
        "Unhandled application exception: %s",
        type(exc).__name__,
    )

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
