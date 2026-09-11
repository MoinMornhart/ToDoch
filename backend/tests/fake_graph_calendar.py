"""Nachgebauter Outlook-Kalender (Microsoft Graph) für Tests – ohne Netzwerk.

Wie Graph mit ``Prefer: outlook.timezone="UTC"``: Zeiten kommen in UTC zurück, ganztägige
Termine aus Europa also als 22:00/23:00 Uhr am Vortag.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

PREFIX = "/v1.0/me/calendar/events"
PAGE = 2


def _utc(value: dict[str, str]) -> dict[str, str]:
    local = datetime.fromisoformat(value["dateTime"][:19])
    zone = value.get("timeZone") or "UTC"
    tz = UTC if zone == "UTC" else ZoneInfo(zone)
    moment = local.replace(tzinfo=tz).astimezone(UTC).replace(tzinfo=None)
    return {"dateTime": moment.isoformat() + ".0000000", "timeZone": "UTC"}


class FakeGraphCalendar:
    def __init__(self) -> None:
        self.token = "access-1"
        self.events: dict[str, dict[str, Any]] = {}
        self.counter = 0
        self.requests: list[tuple[str, str]] = []

    def add(self, **item: Any) -> str:
        self.counter += 1
        remote_id = f"AAMk{self.counter}"
        self.events[remote_id] = {"id": remote_id, **item}
        return remote_id

    def _public(self, item: dict[str, Any]) -> dict[str, Any]:
        result = dict(item)
        result["start"], result["end"] = _utc(item["start"]), _utc(item["end"])
        result["originalStartTimeZone"] = item["start"].get("timeZone", "UTC")
        result["type"] = "seriesMaster" if item.get("recurrence") else "singleInstance"
        return result

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {self.token}"
        assert 'outlook.timezone="UTC"' in request.headers.get("prefer", "")
        path = request.url.path
        assert path.startswith(PREFIX), path
        remote_id = path[len(PREFIX) :].strip("/")
        self.requests.append((request.method, remote_id))
        if request.method == "GET":
            skip = int(request.url.params.get("$skip", "0"))
            items = list(self.events.values())
            body: dict[str, Any] = {"value": [self._public(e) for e in items[skip : skip + PAGE]]}
            if skip + PAGE < len(items):
                body["@odata.nextLink"] = f"https://graph.microsoft.com{PREFIX}?$skip={skip + PAGE}"
            return httpx.Response(200, json=body)
        if request.method == "POST":
            new_id = self.add(**json.loads(request.content))
            return httpx.Response(201, json=self._public(self.events[new_id]))
        if remote_id not in self.events:
            return httpx.Response(404, json={"error": {"code": "ErrorItemNotFound"}})
        if request.method == "PATCH":
            self.events[remote_id].update(json.loads(request.content))
            return httpx.Response(200, json=self._public(self.events[remote_id]))
        if request.method == "DELETE":
            del self.events[remote_id]
            return httpx.Response(204)
        return httpx.Response(405)
