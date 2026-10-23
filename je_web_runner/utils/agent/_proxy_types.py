"""Typed ownership boundary shared by the private browser proxy listener and request handlers."""
from __future__ import annotations

import socket
from typing import Protocol

from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy


class ProxyOwner(Protocol):
    """Only reviewed destinations and explicitly retained sockets belong to this transport."""

    @property
    def policy(self) -> BrowserOriginPolicy:
        """The immutable origin ceiling."""

    def authenticates(self, values: list[str] | None) -> bool:
        """Validate the private proxy credential."""

    def open_upstream(self, url: str) -> socket.socket:
        """Open and retain one reviewed destination."""

    def retain_socket(self, connection: socket.socket) -> None:
        """Register a socket explicitly owned by this listener."""

    def release_socket(self, connection: socket.socket) -> None:
        """Close a retained socket, leaving foreign sockets alone."""


# pylint: disable-next=too-few-public-methods  # reason: this protocol declares the one typed server ownership field
class ProxyListener(Protocol):
    """Typed extension of the stdlib server seam used by handlers."""

    owner: ProxyOwner
