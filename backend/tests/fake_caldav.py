"""Nachgebauter Nextcloud-CalDAV-Server für Tests – ohne Netzwerk.

Wie Nextcloud: ``/.well-known/caldav`` leitet weiter, der Nutzer (principal) nennt sein
Kalender-Verzeichnis, darin ein Terminkalender und eine reine Aufgabenliste.
"""

from __future__ import annotations

import base64

import httpx

from app.services.caldav import calendar_data

ROOT = "/remote.php/dav/"
PRINCIPAL = "/remote.php/dav/principals/users/alice/"
HOME = "/remote.php/dav/calendars/alice/"
PERSONAL = "/remote.php/dav/calendars/alice/personal/"
TASKS = "/remote.php/dav/calendars/alice/tasks/"


def _multistatus(entries: list[tuple[str, str]]) -> httpx.Response:
    body = (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
        'xmlns:c="urn:ietf:params:xml:ns:caldav">'
        + "".join(
            f"<d:response><d:href>{href}</d:href><d:propstat><d:prop>{props}</d:prop>"
            "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
            for href, props in entries
        )
        + "</d:multistatus>"
    )
    return httpx.Response(207, content=body.encode(), headers={"Content-Type": "application/xml"})


def _calendar(name: str, component: str) -> str:
    return (
        "<d:resourcetype><d:collection/><c:calendar/></d:resourcetype>"
        f"<d:displayname>{name}</d:displayname>"
        f'<c:supported-calendar-component-set><c:comp name="{component}"/>'
        "</c:supported-calendar-component-set>"
    )


class FakeCalDav:
    def __init__(self) -> None:
        self.user, self.password = "alice", "app-pass-123"
        self.objects: dict[str, bytes] = {}
        self.requests: list[tuple[str, str]] = []

    def add(self, name: str, ics: str) -> str:
        path = f"{PERSONAL}{name}"
        self.objects[path] = ics.encode()
        return path

    def handler(self, request: httpx.Request) -> httpx.Response:
        credentials = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
        if request.headers.get("authorization") != f"Basic {credentials}":
            return httpx.Response(401, headers={"WWW-Authenticate": 'Basic realm="Nextcloud"'})
        path, method = request.url.path, request.method
        self.requests.append((method, path))
        body = request.content.decode(errors="replace")
        if method == "PROPFIND":
            if path == "/.well-known/caldav":
                return httpx.Response(301, headers={"Location": ROOT})
            if "current-user-principal" in body and path in (ROOT, PRINCIPAL):
                return _multistatus(
                    [
                        (
                            path,
                            f"<d:current-user-principal><d:href>{PRINCIPAL}</d:href>"
                            "</d:current-user-principal>",
                        )
                    ]
                )
            if "calendar-home-set" in body and path == PRINCIPAL:
                return _multistatus(
                    [(path, f"<c:calendar-home-set><d:href>{HOME}</d:href></c:calendar-home-set>")]
                )
            if "resourcetype" in body and path == HOME and request.headers.get("depth") == "1":
                return _multistatus(
                    [
                        (HOME, "<d:resourcetype><d:collection/></d:resourcetype>"),
                        (PERSONAL, _calendar("Persönlich", "VEVENT")),
                        (TASKS, _calendar("Aufgaben", "VTODO")),
                    ]
                )
            if "resourcetype" in body and path == PERSONAL:
                return _multistatus([(PERSONAL, _calendar("Persönlich", "VEVENT"))])
            if path in (ROOT, PRINCIPAL):
                return _multistatus([(path, "<d:resourcetype><d:collection/></d:resourcetype>")])
            return httpx.Response(404)
        if method == "REPORT" and path == PERSONAL:
            return _multistatus(
                [
                    (
                        href,
                        f'<d:getetag>"{len(data)}"</d:getetag>'
                        f"<c:calendar-data>{calendar_data(data)}</c:calendar-data>",
                    )
                    for href, data in self.objects.items()
                ]
            )
        if method == "GET":
            if path not in self.objects:
                return httpx.Response(404)
            return httpx.Response(200, content=self.objects[path])
        if method == "PUT" and path.startswith(PERSONAL):
            if request.headers.get("if-none-match") == "*" and path in self.objects:
                return httpx.Response(412)
            created = path not in self.objects
            self.objects[path] = request.content
            return httpx.Response(201 if created else 204)
        if method == "DELETE":
            return httpx.Response(204 if self.objects.pop(path, None) is not None else 404)
        return httpx.Response(405)
