"""
Real-device 雲端連線：在既有 cloud_grid 上補上行動裝置 caps、session
metadata、test status 回寫、env-var 認證。

Adds three things the existing :mod:`cloud_grid` module doesn't cover:

* **Real-device capabilities** — BrowserStack App-Automate / Sauce RDC /
  LambdaTest Real-Device style caps (``deviceName``, ``platformVersion``,
  ``realMobile`` toggles).
* **Session metadata** — pull the dashboard URL + video URL of a started
  session so the report can link directly to it.
* **Status update** — write pass/fail/reason back to the provider so the
  cloud dashboard isn't perpetually "running".

Credentials are loaded from env vars by default (so they never have to be
typed into action JSON):

* BrowserStack: ``BROWSERSTACK_USERNAME``, ``BROWSERSTACK_ACCESS_KEY``
* Sauce Labs:   ``SAUCE_USERNAME``, ``SAUCE_ACCESS_KEY``
* LambdaTest:   ``LT_USERNAME``, ``LT_ACCESS_KEY``
"""
from __future__ import annotations

import json
import os
import ssl
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class DeviceCloudError(WebRunnerException):
    """Raised on connection / status update / metadata fetch errors."""


SUPPORTED_PROVIDERS: Tuple[str, ...] = ("browserstack", "saucelabs", "lambdatest")


_ENV_VAR_MAP: Dict[str, Tuple[str, str]] = {
    "browserstack": ("BROWSERSTACK_USERNAME", "BROWSERSTACK_ACCESS_KEY"),
    "saucelabs": ("SAUCE_USERNAME", "SAUCE_ACCESS_KEY"),
    "lambdatest": ("LT_USERNAME", "LT_ACCESS_KEY"),
}

_REST_BASES: Dict[str, str] = {
    "browserstack": "https://api.browserstack.com",
    "saucelabs": "https://api.us-west-1.saucelabs.com",
    "lambdatest": "https://api.lambdatest.com",
}

_DASHBOARD_BASES: Dict[str, str] = {
    "browserstack": "https://automate.browserstack.com/dashboard/v2/sessions",
    "saucelabs": "https://app.saucelabs.com/tests",
    "lambdatest": "https://automation.lambdatest.com/test",
}


# ---------- credentials --------------------------------------------------

@dataclass(frozen=True)
class CloudCredentials:
    """Cloud provider credentials. Never logged, never serialised."""

    username: str
    access_key: str

    def redacted(self) -> Dict[str, str]:
        return {
            "username": self.username,
            "access_key": "***" if self.access_key else "",
        }


def _normalise_provider(provider: str) -> str:
    normalised = (provider or "").lower().strip()
    if normalised not in SUPPORTED_PROVIDERS:
        raise DeviceCloudError(
            f"unsupported provider {provider!r}; expected one of {SUPPORTED_PROVIDERS}"
        )
    return normalised


def load_credentials(provider: str) -> CloudCredentials:
    """
    從環境變數讀取對應 provider 的 credentials。
    Read credentials from env vars, raising if either is missing. Use this
    in CI to avoid putting secrets into action JSON.
    """
    key = _normalise_provider(provider)
    user_var, access_var = _ENV_VAR_MAP[key]
    username = os.environ.get(user_var, "")
    access_key = os.environ.get(access_var, "")
    if not username or not access_key:
        raise DeviceCloudError(
            f"missing credentials for {key!r}: set {user_var} and {access_var}"
        )
    return CloudCredentials(username=username, access_key=access_key)


# ---------- capability builders -----------------------------------------

@dataclass
class RealDeviceCaps:
    """
    Common spec for a real-device session, converted per provider on demand.
    Keeping this provider-neutral lets callers swap clouds without rewriting.
    """

    device_name: str
    platform_name: str  # "iOS" | "Android"
    platform_version: str
    browser_name: str = "Chrome"  # or "Safari" on iOS
    real_mobile: bool = True
    build: Optional[str] = None
    name: Optional[str] = None
    project: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


def _to_browserstack(caps: RealDeviceCaps) -> Dict[str, Any]:
    bstack: Dict[str, Any] = {
        "deviceName": caps.device_name,
        "osVersion": caps.platform_version,
        "realMobile": "true" if caps.real_mobile else "false",
    }
    if caps.project:
        bstack["projectName"] = caps.project
    if caps.build:
        bstack["buildName"] = caps.build
    if caps.name:
        bstack["sessionName"] = caps.name
    out: Dict[str, Any] = {
        "browserName": caps.browser_name,
        "platformName": caps.platform_name,
        "bstack:options": bstack,
    }
    out.update(caps.extra)
    return out


def _to_saucelabs(caps: RealDeviceCaps) -> Dict[str, Any]:
    sauce: Dict[str, Any] = {}
    if caps.build:
        sauce["build"] = caps.build
    if caps.name:
        sauce["name"] = caps.name
    appium_caps: Dict[str, Any] = {
        "appium:deviceName": caps.device_name,
        "appium:platformVersion": caps.platform_version,
        "appium:automationName": "XCUITest" if caps.platform_name.lower() == "ios" else "UiAutomator2",
    }
    out: Dict[str, Any] = {
        "browserName": caps.browser_name,
        "platformName": caps.platform_name,
        "sauce:options": sauce,
        **appium_caps,
    }
    out.update(caps.extra)
    return out


def _to_lambdatest(caps: RealDeviceCaps) -> Dict[str, Any]:
    lt: Dict[str, Any] = {
        "deviceName": caps.device_name,
        "platformVersion": caps.platform_version,
        "isRealMobile": caps.real_mobile,
    }
    if caps.build:
        lt["build"] = caps.build
    if caps.name:
        lt["name"] = caps.name
    if caps.project:
        lt["project"] = caps.project
    out: Dict[str, Any] = {
        "browserName": caps.browser_name,
        "platformName": caps.platform_name,
        "LT:Options": lt,
    }
    out.update(caps.extra)
    return out


_CAPS_DISPATCH: Dict[str, Callable[[RealDeviceCaps], Dict[str, Any]]] = {
    "browserstack": _to_browserstack,
    "saucelabs": _to_saucelabs,
    "lambdatest": _to_lambdatest,
}


def build_capabilities(provider: str, caps: RealDeviceCaps) -> Dict[str, Any]:
    """Project a :class:`RealDeviceCaps` into provider-native capabilities."""
    key = _normalise_provider(provider)
    return _CAPS_DISPATCH[key](caps)


# ---------- connect with retry ------------------------------------------

@dataclass
class CloudSession:
    """Metadata about a started cloud session."""

    provider: str
    session_id: str
    dashboard_url: str
    video_url: Optional[str] = None
    status: str = "running"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _dashboard_url(provider: str, session_id: str) -> str:
    base = _DASHBOARD_BASES[provider]
    if provider == "browserstack":
        return f"{base}/{session_id}"
    if provider == "saucelabs":
        return f"{base}/{session_id}"
    return f"{base}?testID={session_id}"


def connect_real_device(
    provider: str,
    caps: RealDeviceCaps,
    *,
    credentials: Optional[CloudCredentials] = None,
    retries: int = 2,
    backoff_seconds: float = 3.0,
    connector: Optional[Callable[..., Any]] = None,
) -> Tuple[Any, CloudSession]:
    """
    開一個 real-device session，回傳 (driver, CloudSession)。
    Connect to a cloud provider's real-device cloud with retries. Returns
    the Selenium ``Remote`` driver and a :class:`CloudSession` carrying the
    session id and dashboard URL.

    ``connector`` is the underlying connect function; defaults to the
    relevant ``cloud_drivers.connect_*`` helper so tests can inject a fake.
    """
    key = _normalise_provider(provider)
    creds = credentials or load_credentials(key)
    capabilities = build_capabilities(key, caps)
    web_runner_logger.info(
        f"connect_real_device provider={key} device={caps.device_name!r} "
        f"build={caps.build!r} creds={creds.redacted()}"
    )

    chosen = connector or _default_connector(key)
    last_error: Optional[Exception] = None
    for attempt in range(max(1, retries + 1)):
        try:
            driver = chosen(creds.username, creds.access_key, capabilities)
            session_id = getattr(driver, "session_id", None) or ""
            if not session_id:
                raise DeviceCloudError("driver returned without a session_id")
            session = CloudSession(
                provider=key,
                session_id=session_id,
                dashboard_url=_dashboard_url(key, session_id),
            )
            return driver, session
        except Exception as error:  # noqa: BLE001 — cloud connect surface varies
            last_error = error
            web_runner_logger.warning(
                f"connect_real_device attempt {attempt + 1} failed: {error!r}"
            )
            if attempt < retries:
                time.sleep(backoff_seconds * (attempt + 1))
    raise DeviceCloudError(
        f"connect_real_device failed after {retries + 1} attempts: {last_error!r}"
    ) from last_error


def _default_connector(provider: str) -> Callable[..., Any]:
    from je_web_runner.utils.cloud_grid.cloud_drivers import (
        connect_browserstack,
        connect_lambdatest,
        connect_saucelabs,
    )
    return {
        "browserstack": connect_browserstack,
        "saucelabs": connect_saucelabs,
        "lambdatest": connect_lambdatest,
    }[provider]


# ---------- REST helpers -------------------------------------------------

def _basic_auth_header(creds: CloudCredentials) -> str:
    import base64
    raw = f"{creds.username}:{creds.access_key}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _rest_request(
    method: str,
    url: str,
    credentials: CloudCredentials,
    payload: Optional[Dict[str, Any]] = None,
    timeout: float = 15.0,
) -> Any:
    if not url.startswith("https://"):
        raise DeviceCloudError(f"refusing non-https URL: {url!r}")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", _basic_auth_header(credentials))
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(  # nosec B310 — https-only enforced above
            req, timeout=timeout, context=context,
        ) as response:
            body = response.read().decode("utf-8")
    except (OSError, ValueError) as error:
        raise DeviceCloudError(f"REST call failed: {error!r}") from error
    if not body:
        return None
    try:
        return json.loads(body)
    except ValueError as error:
        raise DeviceCloudError(f"non-JSON response: {error}") from error


def _session_info_url(provider: str, session_id: str) -> str:
    base = _REST_BASES[provider]
    if provider == "browserstack":
        return f"{base}/automate/sessions/{session_id}.json"
    if provider == "saucelabs":
        return f"{base}/rest/v1.1/jobs/{session_id}"
    return f"{base}/automation/api/v1/sessions/{session_id}"


def _session_status_url(provider: str, session_id: str) -> str:
    base = _REST_BASES[provider]
    if provider == "browserstack":
        return f"{base}/automate/sessions/{session_id}.json"
    if provider == "saucelabs":
        return f"{base}/rest/v1.1/jobs/{session_id}"
    return f"{base}/automation/api/v1/sessions/{session_id}"


def fetch_session_info(
    provider: str,
    session_id: str,
    credentials: Optional[CloudCredentials] = None,
    *,
    request_fn: Optional[Callable[..., Any]] = None,
) -> CloudSession:
    """
    讀取 session 的 metadata，補上 video URL 與目前 status。
    Fetch session metadata so the report can include the dashboard + video.
    ``request_fn`` lets tests stub out the HTTP call.
    """
    key = _normalise_provider(provider)
    creds = credentials or load_credentials(key)
    url = _session_info_url(key, session_id)
    caller = request_fn or _rest_request
    payload = caller("GET", url, creds)
    if not isinstance(payload, dict):
        raise DeviceCloudError(f"unexpected session info payload: {type(payload).__name__}")
    return CloudSession(
        provider=key,
        session_id=session_id,
        dashboard_url=_dashboard_url(key, session_id),
        video_url=_extract_video_url(key, payload),
        status=_extract_status(key, payload),
    )


def _extract_video_url(provider: str, payload: Dict[str, Any]) -> Optional[str]:
    if provider == "browserstack":
        info = payload.get("automation_session") or {}
        url = info.get("video_url")
        if isinstance(url, str):
            return url
    if provider == "saucelabs":
        url = payload.get("video_url")
        if isinstance(url, str):
            return url
    if provider == "lambdatest":
        data = payload.get("data") or payload
        url = data.get("video_url") if isinstance(data, dict) else None
        if isinstance(url, str):
            return url
    return None


def _extract_status(provider: str, payload: Dict[str, Any]) -> str:
    if provider == "browserstack":
        info = payload.get("automation_session") or {}
        return str(info.get("status") or "unknown")
    if provider == "saucelabs":
        return str(payload.get("status") or "unknown")
    data = payload.get("data") or payload
    if isinstance(data, dict):
        return str(data.get("status_ind") or data.get("status") or "unknown")
    return "unknown"


def update_session_status(
    provider: str,
    session_id: str,
    *,
    passed: bool,
    reason: Optional[str] = None,
    credentials: Optional[CloudCredentials] = None,
    request_fn: Optional[Callable[..., Any]] = None,
) -> None:
    """
    把測試結果回寫到 provider，讓 dashboard 從 running 變 passed / failed。
    Write the final status back so the cloud dashboard reflects reality.
    """
    key = _normalise_provider(provider)
    creds = credentials or load_credentials(key)
    url = _session_status_url(key, session_id)
    caller = request_fn or _rest_request
    if key == "browserstack":
        payload = {
            "status": "passed" if passed else "failed",
            "reason": reason or "",
        }
        caller("PUT", url, creds, payload)
        return
    if key == "saucelabs":
        payload = {
            "passed": bool(passed),
            "name": reason or "",
        }
        caller("PUT", url, creds, payload)
        return
    # lambdatest
    payload = {
        "status_ind": "passed" if passed else "failed",
        "reason": reason or "",
    }
    caller("PATCH", url, creds, payload)


# ---------- small report helper -----------------------------------------

def session_summary_markdown(session: CloudSession) -> str:
    """Render the session metadata as a markdown bullet list for reports."""
    pieces = [
        f"- **Provider:** {session.provider}",
        f"- **Session ID:** `{session.session_id}`",
        f"- **Dashboard:** [{session.dashboard_url}]({session.dashboard_url})",
    ]
    if session.video_url:
        pieces.append(f"- **Video:** [{session.video_url}]({session.video_url})")
    pieces.append(f"- **Status:** `{session.status}`")
    return "\n".join(pieces) + "\n"
