"""
testcontainers 整合：以 Python 啟動暫存的 Postgres / Redis / 通用 Docker container。
testcontainers-python wrappers. Useful for tests that need a real
Postgres / Redis up for a single run.

``testcontainers`` 為軟相依。
``testcontainers`` is a soft dependency.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class TestcontainersError(WebRunnerException):
    """Raised when testcontainers is missing or a container fails to start."""


_started: List[Any] = []


def _require(module: str, attribute: str) -> Any:
    """Lazy import a single attribute from a testcontainers submodule."""
    try:
        imported = __import__(f"testcontainers.{module}", fromlist=[attribute])
        return getattr(imported, attribute)
    except ImportError as error:
        raise TestcontainersError(
            "testcontainers is not installed. "
            "Install with: pip install testcontainers"
        ) from error
    except AttributeError as error:
        raise TestcontainersError(
            f"testcontainers.{module} has no attribute {attribute!r}"
        ) from error


def start_postgres(
    image: str = "postgres:16-alpine",
    user: str = "test",
    password: str = "test",  # NOSONAR  # nosec B107 — testcontainers default
    dbname: str = "test",
) -> Any:
    """
    啟動暫存 Postgres，回傳 container 實例（含 ``get_connection_url()``）
    Start a Postgres container and return the testcontainers handle.
    """
    web_runner_logger.info(f"start_postgres image={image}")
    postgres_cls = _require("postgres", "PostgresContainer")
    container = postgres_cls(image, user=user, password=password, dbname=dbname)
    container.start()
    _started.append(container)
    return container


def start_redis(image: str = "redis:7-alpine") -> Any:
    web_runner_logger.info(f"start_redis image={image}")
    redis_cls = _require("redis", "RedisContainer")
    container = redis_cls(image)
    container.start()
    _started.append(container)
    return container


def start_generic(image: str, ports: Optional[Dict[int, int]] = None) -> Any:
    """
    啟動任意 Docker image
    Start any Docker image. ``ports`` is a {container_port: host_port} map.
    """
    web_runner_logger.info(f"start_generic image={image}")
    docker_cls = _require("core.container", "DockerContainer")
    container = docker_cls(image)
    if ports:
        for container_port, host_port in ports.items():
            container.with_bind_ports(int(container_port), int(host_port))
    container.start()
    _started.append(container)
    return container


def stop_container(container: Any) -> None:
    """Stop a single container started by this module."""
    try:
        container.stop()
    finally:
        if container in _started:
            _started.remove(container)


def cleanup_all() -> None:
    """Stop every container started by this module."""
    web_runner_logger.info(f"cleanup_all: {len(_started)} containers")
    while _started:
        container = _started.pop()
        try:
            container.stop()
        except Exception as error:  # noqa: BLE001 — keep cleaning up the rest
            web_runner_logger.warning(f"failed to stop container: {error!r}")


def started_count() -> int:
    """How many containers are tracked as live by this module."""
    return len(_started)
