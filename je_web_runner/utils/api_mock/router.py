"""
HTTP 路由 mocking：給 Playwright ``page.route()`` 包一層宣告式 API。
Declarative API for HTTP route mocking. Each :class:`MockRoute` is a
``(method, url_pattern, response)`` triple; :class:`MockRouter` keeps an
ordered list and matches the first hit.

Designed to drive ``page.route(pattern, handler)`` in Playwright; the
matcher is also usable for unit tests via :meth:`MockRouter.match`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ApiMockError(WebRunnerException):
    """Raised when route configuration is invalid."""


_HttpStatus = int


@dataclass
class MockResponse:
    """Static response payload."""

    status: _HttpStatus = 200
    body: Any = ""
    headers: Dict[str, str] = field(default_factory=dict)
    content_type: str = "application/json"

    def to_payload(self) -> Dict[str, Any]:
        if isinstance(self.body, (dict, list)):
            body_text = json.dumps(self.body, ensure_ascii=False)
        else:
            body_text = str(self.body)
        headers = dict(self.headers)
        headers.setdefault("content-type", self.content_type)
        return {"status": self.status, "headers": headers, "body": body_text}


@dataclass
class MockRoute:
    """Single matcher + response."""

    method: str
    url_pattern: str
    response: MockResponse
    times: Optional[int] = None
    times_seen: int = 0

    def matches(self, method: str, url: str) -> bool:
        if self.method.upper() != method.upper() and self.method != "*":
            return False
        return _url_matches(self.url_pattern, url)

    def consume(self) -> bool:
        if self.times is None:
            return True
        if self.times_seen >= self.times:
            return False
        self.times_seen += 1
        return True


def _url_matches(pattern: str, url: str) -> bool:
    if pattern == url:
        return True
    if "*" in pattern:
        regex = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
        return re.match(regex, url) is not None
    if pattern.startswith("re:"):
        try:
            return re.search(pattern[3:], url) is not None
        except re.error as error:
            raise ApiMockError(f"invalid regex pattern: {pattern!r}") from error
    return False


class MockRouter:
    """Ordered list of :class:`MockRoute`."""

    def __init__(self) -> None:
        self._routes: List[MockRoute] = []
        self._calls: List[Tuple[str, str]] = []

    def add(
        self,
        method: str,
        url_pattern: str,
        body: Any = "",
        status: int = 200,
        headers: Optional[Dict[str, str]] = None,
        content_type: str = "application/json",
        times: Optional[int] = None,
    ) -> MockRoute:
        if not isinstance(method, str) or not method:
            raise ApiMockError("method must be a non-empty string")
        if not isinstance(url_pattern, str) or not url_pattern:
            raise ApiMockError("url_pattern must be a non-empty string")
        route = MockRoute(
            method=method,
            url_pattern=url_pattern,
            response=MockResponse(
                status=status,
                body=body,
                headers=headers or {},
                content_type=content_type,
            ),
            times=times,
        )
        self._routes.append(route)
        return route

    def match(self, method: str, url: str) -> Optional[MockRoute]:
        self._calls.append((method.upper(), url))
        for route in self._routes:
            if route.matches(method, url) and route.consume():
                return route
        return None

    def calls(self) -> List[Tuple[str, str]]:
        return list(self._calls)

    def attach_to_page(self, page: Any) -> None:
        """Wire the router onto a Playwright page via ``page.route('**/*')``."""
        if not hasattr(page, "route"):
            raise ApiMockError("page does not expose route() — Playwright only")

        def _handler(route: Any, request: Any) -> None:
            method = getattr(request, "method", "GET")
            url = getattr(request, "url", "")
            matched = self.match(method, url)
            if matched is None:
                route.continue_()
                return
            payload = matched.response.to_payload()
            try:
                route.fulfill(
                    status=payload["status"],
                    headers=payload["headers"],
                    body=payload["body"],
                )
            except Exception as error:  # pylint: disable=broad-except
                web_runner_logger.warning(
                    f"api_mock fulfill failed: {error!r}; falling back to continue"
                )
                route.continue_()

        page.route("**/*", _handler)


_GLOBAL = MockRouter()


def register_route(
    method: str,
    url_pattern: str,
    body: Union[str, Dict[str, Any], List[Any]] = "",
    status: int = 200,
    times: Optional[int] = None,
) -> MockRoute:
    """Register a route on the module-level singleton."""
    return _GLOBAL.add(method, url_pattern, body=body, status=status, times=times)


def reset_global_router() -> None:
    """Clear all registered routes and call history."""
    _GLOBAL._routes.clear()  # pylint: disable=protected-access
    _GLOBAL._calls.clear()  # pylint: disable=protected-access


def global_router() -> MockRouter:
    return _GLOBAL
