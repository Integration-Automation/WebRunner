"""
為瀏覽器設定 geolocation / timezone / locale；產出 CDP 與 Playwright 兩種 payload。
Geolocation, timezone, and locale override helpers. Returns CDP commands
(``Emulation.setGeolocationOverride`` / ``setTimezoneOverride`` /
``setLocaleOverride``) and Playwright ``new_context`` kwargs from a single
:class:`GeoOverride` value.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class GeoLocaleError(WebRunnerException):
    """Raised when override parameters are invalid or driver unsupported."""


@dataclass(frozen=True)
class GeoOverride:
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy_meters: float = 50.0
    timezone: Optional[str] = None
    locale: Optional[str] = None

    def validate(self) -> None:
        if (self.latitude is None) ^ (self.longitude is None):
            raise GeoLocaleError("latitude and longitude must be set together")
        if self.latitude is not None and not -90.0 <= self.latitude <= 90.0:
            raise GeoLocaleError(f"latitude out of range: {self.latitude}")
        if self.longitude is not None and not -180.0 <= self.longitude <= 180.0:
            raise GeoLocaleError(f"longitude out of range: {self.longitude}")
        if self.timezone is not None and (not isinstance(self.timezone, str)
                                          or "/" not in self.timezone):
            raise GeoLocaleError(f"timezone must be IANA-shaped: {self.timezone!r}")
        if self.locale is not None and (not isinstance(self.locale, str)
                                        or len(self.locale) < 2):
            raise GeoLocaleError(f"locale must be like 'en-US': {self.locale!r}")


def cdp_payloads(override: GeoOverride) -> List[Dict[str, Any]]:
    """Return a list of ``(method, params)`` CDP commands."""
    override.validate()
    payloads: List[Dict[str, Any]] = []
    if override.latitude is not None and override.longitude is not None:
        payloads.append({
            "method": "Emulation.setGeolocationOverride",
            "params": {
                "latitude": override.latitude,
                "longitude": override.longitude,
                "accuracy": override.accuracy_meters,
            },
        })
    if override.timezone is not None:
        payloads.append({
            "method": "Emulation.setTimezoneOverride",
            "params": {"timezoneId": override.timezone},
        })
    if override.locale is not None:
        payloads.append({
            "method": "Emulation.setLocaleOverride",
            "params": {"locale": override.locale},
        })
    return payloads


def playwright_context_kwargs(override: GeoOverride) -> Dict[str, Any]:
    """Return ``new_context`` kwargs for Playwright."""
    override.validate()
    kwargs: Dict[str, Any] = {}
    if override.latitude is not None and override.longitude is not None:
        kwargs["geolocation"] = {
            "latitude": override.latitude,
            "longitude": override.longitude,
            "accuracy": override.accuracy_meters,
        }
        kwargs["permissions"] = ["geolocation"]
    if override.timezone is not None:
        kwargs["timezone_id"] = override.timezone
    if override.locale is not None:
        kwargs["locale"] = override.locale
    return kwargs


def apply_overrides(driver: Any, override: GeoOverride) -> List[str]:
    """
    對 Selenium driver 透過 ``execute_cdp_cmd`` 套用所有 override
    Issue every CDP command from :func:`cdp_payloads`. Returns the list of
    method names actually invoked.
    """
    if not hasattr(driver, "execute_cdp_cmd"):
        raise GeoLocaleError("driver does not expose execute_cdp_cmd")
    methods: List[str] = []
    for command in cdp_payloads(override):
        driver.execute_cdp_cmd(command["method"], command["params"])
        methods.append(command["method"])
    return methods
