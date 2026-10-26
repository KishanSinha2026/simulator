"""Convenience entry point for running the FastAPI application."""

import os

import uvicorn


def _get_port() -> int:
    """Read and validate the application port."""
    raw_port = os.getenv("APP_PORT", "8000")

    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError("APP_PORT must be an integer") from exc

    if not 1 <= port <= 65535:
        raise ValueError("APP_PORT must be between 1 and 65535")

    return port


def _get_bool(name: str, default: str = "false") -> bool:
    """Parse a boolean environment variable."""
    value = os.getenv(name, default).strip().lower()

    if value in {"true", "1", "yes", "on"}:
        return True

    if value in {"false", "0", "no", "off"}:
        return False

    raise ValueError(
        f"{name} must be a boolean value, such as true or false"
    )


def main() -> None:
    """Start the application using Uvicorn."""
    host = os.getenv("APP_HOST", "127.0.0.1").strip()

    if not host:
        raise ValueError("APP_HOST cannot be empty")

    log_level = os.getenv("LOG_LEVEL", "info").strip().lower()
    allowed_log_levels = {
        "critical",
        "error",
        "warning",
        "info",
        "debug",
        "trace",
    }

    if log_level not in allowed_log_levels:
        raise ValueError(
            f"LOG_LEVEL must be one of: "
            f"{', '.join(sorted(allowed_log_levels))}"
        )

    uvicorn.run(
        "app.main:app",
        host=host,
        port=_get_port(),
        reload=_get_bool("APP_RELOAD"),
        log_level=log_level,
    )


if __name__ == "__main__":
    main()