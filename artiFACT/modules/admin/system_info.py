"""Version, deploy SHA, uptime, environment name."""

import os
import time

_START_TIME = time.monotonic()


def get_app_version() -> str:
    """Return application version."""
    return "0.1.0"


def get_deploy_sha() -> str:
    """Return git SHA from environment or 'dev'."""
    return os.environ.get("DEPLOY_SHA", "dev")


def get_uptime() -> float:
    """Return seconds since process started."""
    return round(time.monotonic() - _START_TIME, 1)


def get_env_name() -> str:
    """Return environment name (development, staging, production)."""
    return os.environ.get("APP_ENV", "development")
