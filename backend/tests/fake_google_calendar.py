"""Nachgebauter Google Kalender (Calendar API v3) für Tests – ohne Netzwerk."""

from __future__ import annotations

import json
from typing import Any

import httpx

PREFIX = "/calendar/v3/calendars/primary/events"


class FakeGoogleCalendar:
    def __init__(self) -> None:
        self.token = "access-1"
        self.events: dict[str, dict[str, Any]] = {}
        self.version = 0
        self.counter = 0
        self.expire_sync_token = False
        self.requests: list[tuple[str, str]] = []

    def _touch(self, item: dict[str, Any]) -> None:
        self.version += 1
        item["_v"] = self.version

    def add(self, **item: Any) -> str:
        self.counter += 1
        remote_id = f"g{self.counter}"
        entry = {"id": remote_id, "status": "confirmed", **item}
        self._touch(entry)
        self.events[remote_id] = entry
        return remote_id

    def change(self, remote_id: str, **fields: Any) -> None:
        self.events[remote_id].update(fields)
        self._touch(self.events[remote_id])

    def remove(self, remote_id: str) -> None:
        self.change(remote_id, status="cancelled")

    def live(self) -> dict[str, dict[str, Any]]:
        return {k: v for k, v in self.events.items() if v["status"] != "cancelled"}

    @staticmethod
    def _public(item: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in item.items() if not k.startswith("_")}

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {self.token}"
        path = request.url.path
        assert path.startswith(PREFIX), path
        remote_id = path[len(PREFIX) :].strip("/")
        self.requests.append((request.method, remote_id))
        if request.method == "GET":
            params = request.url.params
            if params.get("syncToken"):
                if self.expire_sync_token:
                    self.expire_sync_token = False
                    return httpx.Response(410, json={"error": {"code": 410}})
                since = int(params["syncToken"])
                items = [e for e in self.events.values() if e["_v"] > since]
            else:
                items = [e for e in self.events.values() if e["status"] != "cancelled"]
            body = {"items": [self._public(e) for e in items], "nextSyncToken": str(self.version)}
            return httpx.Response(200, json=body)
        if request.method == "POST":
            data = json.loads(request.content)
            new_id = self.add(**data)
            return httpx.Response(200, json=self._public(self.events[new_id]))
        if request.method == "PATCH":
            if remote_id not in self.live():
                return httpx.Response(404, json={"error": {"code": 404}})
            self.change(remote_id, **json.loads(request.content))
            return httpx.Response(200, json=self._public(self.events[remote_id]))
        if request.method == "DELETE":
            if remote_id not in self.live():
                return httpx.Response(410, json={"error": {"code": 410}})
            self.remove(remote_id)
            return httpx.Response(204)
        return httpx.Response(405)
