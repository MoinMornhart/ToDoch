"""Verbindungen zu Adressen von Nutzern gehen genau an die geprüfte IP (kein DNS-Rebinding)."""

from collections.abc import Iterable
from typing import Any

import httpcore
import pytest

from app.services import external_calendars as feeds

# Vor dem Autouse-Fixture in conftest gemerkt, das den Abruf im Test sonst ersetzt
REAL_FETCH = feeds.fetch_ics


class RecordingBackend(httpcore.AsyncNetworkBackend):
    """Merkt sich, wohin verbunden werden soll – und verbindet nie wirklich."""

    def __init__(self) -> None:
        self.hosts: list[str] = []

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,  # noqa: ASYNC109 – Schnittstelle von httpcore
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        self.hosts.append(host)
        raise httpcore.ConnectError("Testnetz")


def answers(monkeypatch: pytest.MonkeyPatch, *results: list[str]) -> list[str]:
    """Die Namensauflösung liefert nacheinander ``results``; gibt die gefragten Namen zurück."""
    asked: list[str] = []
    queue = list(results)

    async def fake_resolve(host: str, port: int) -> list[str]:
        asked.append(host)
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(feeds, "resolve", fake_resolve)
    return asked


async def test_connects_to_the_checked_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    answers(monkeypatch, ["93.184.216.34", "93.184.216.35"])
    backend = feeds.PinnedBackend(allow_private=False)
    recorder = RecordingBackend()
    backend.inner = recorder
    with pytest.raises(httpcore.ConnectError):
        await backend.connect_tcp("calendar.example", 443)
    # Beide geprüften IPs versucht – nie der Name, den das Betriebssystem neu auflösen würde
    assert recorder.hosts == ["93.184.216.34", "93.184.216.35"]


async def test_blocked_address_never_connects(monkeypatch: pytest.MonkeyPatch) -> None:
    answers(monkeypatch, ["192.168.178.1"])
    backend = feeds.PinnedBackend(allow_private=False)
    recorder = RecordingBackend()
    backend.inner = recorder
    with pytest.raises(httpcore.ConnectError, match="eigenen Netz"):
        await backend.connect_tcp("router.example", 80)
    assert recorder.hosts == []
    with pytest.raises(httpcore.ConnectError):
        await backend.connect_unix_socket("/var/run/docker.sock")


async def test_dns_rebinding_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    # Erst eine öffentliche Adresse (Prüfung bestanden), beim Verbinden dann Loopback
    asked = answers(monkeypatch, ["93.184.216.34"], ["127.0.0.1"])
    with pytest.raises(feeds.FeedError, match="nicht erreichbar"):
        await REAL_FETCH("https://rebind.example/a.ics", allow_private=True)
    assert asked == ["rebind.example", "rebind.example"]


def test_pinned_transport_uses_the_backend() -> None:
    # Hängt an httpx-Interna – bricht ein Update das, soll es hier auffallen, nicht im Betrieb
    transport = feeds.pinned_transport(allow_private=True)
    assert isinstance(transport._pool._network_backend, feeds.PinnedBackend)
