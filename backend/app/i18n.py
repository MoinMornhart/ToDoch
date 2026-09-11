"""Meldungen des Servers auf Englisch – je nach ``Accept-Language`` (Standard: Deutsch).

Die Meldungen stehen im Code auf Deutsch; hier liegt die englische Fassung. Ein Test prüft,
dass jede Meldung im Code eine Übersetzung hat (tests/test_i18n.py).
"""

from __future__ import annotations

import re
from collections.abc import Callable

Language = str

EXACT: dict[str, str] = {
    "Nicht gefunden.": "Not found.",
    "Keine Berechtigung.": "Permission denied.",
    "Bitte anmelden.": "Please sign in.",
    "E-Mail-Adresse oder Passwort ist falsch.": "Email address or password is incorrect.",
    "Anmeldung mit Passkey fehlgeschlagen.": "Passkey sign-in failed.",
    "Zu viele Versuche. Bitte später erneut versuchen.": (
        "Too many attempts. Please try again later."
    ),
    "Die Anfrage ist zu groß.": "The request is too large.",
    "Die Herkunft der Anfrage ist nicht erlaubt.": "The origin of this request is not allowed.",
    "CSRF-Prüfung fehlgeschlagen. Bitte die Seite neu laden.": (
        "CSRF check failed. Please reload the page."
    ),
    "Bitte das aktuelle Passwort eingeben.": "Please enter your current password.",
    "Das aktuelle Passwort ist falsch.": "The current password is incorrect.",
    "Das Passwort ist falsch.": "The password is incorrect.",
    "Das Passwort ist zu einfach.": "The password is too simple.",
    "Das Passwort darf weder Namen noch E-Mail-Adresse enthalten.": (
        "The password must not contain your name or email address."
    ),
    "Dieses Passwort taucht in Listen gestohlener Passwörter auf. Bitte ein anderes wählen.": (
        "This password appears in lists of stolen passwords. Please choose another one."
    ),
    "Einrichtungscode fehlt. Auf dem Server 'todoch setup-code' ausführen.": (
        "Setup code missing. Run 'todoch setup-code' on the server."
    ),
    "Der Einrichtungscode ist falsch.": "The setup code is incorrect.",
    "ToDoch ist bereits eingerichtet.": "ToDoch is already set up.",
    "Die Anfrage ist abgelaufen. Bitte erneut versuchen.": (
        "The request has expired. Please try again."
    ),
    "Der Passkey konnte nicht geprüft werden.": "The passkey could not be verified.",
    "Dieser Passkey ist schon eingetragen.": "This passkey is already registered.",
    "Diesen Bereich gibt es schon.": "This area already exists.",
    "Der letzte Bereich kann nicht gelöscht werden.": "The last area cannot be deleted.",
    "Der Bereich enthält noch Aufgaben. Bitte einen Zielbereich wählen.": (
        "The area still contains tasks. Please choose a target area."
    ),
    "Zielbereich muss ein anderer sein.": "The target area must be a different one.",
    "Der Kalender muss vor dem Ende beginnen.": "The calendar must start before it ends.",
    "Bitte zuerst einen Bereich anlegen.": "Please create an area first.",
    "Bitte eine Uhrzeit angeben oder „ganztägig“ wählen.": (
        "Please enter a time or choose “all day”."
    ),
    "Das Ende liegt vor dem Beginn.": "The end is before the start.",
    "Eine Uhrzeit braucht ein Datum.": "A time needs a date.",
    "Dieses Vorkommen gehört nicht zur Serie.": "This occurrence does not belong to the series.",
    "Link muss mit http:// oder https:// beginnen": "Link must start with http:// or https://",
    "Unbekannte Zeitzone": "Unknown time zone",
    "Der Code ist falsch.": "The code is incorrect.",
    "Die Anmeldung ist abgelaufen. Bitte erneut anmelden.": (
        "The sign-in has expired. Please sign in again."
    ),
    "Zwei-Faktor ist bereits eingerichtet.": "Two-factor authentication is already set up.",
    "Zwei-Faktor ist nicht eingerichtet.": "Two-factor authentication is not set up.",
    "Die Einrichtung ist abgelaufen. Bitte neu beginnen.": (
        "The setup has expired. Please start again."
    ),
    "Die Adresse ist ungültig.": "The address is invalid.",
    "Die Adresse muss mit http:// oder https:// beginnen.": (
        "The address must start with http:// or https://."
    ),
    "Der Name der Adresse lässt sich nicht auflösen.": (
        "The address's host name cannot be resolved."
    ),
    "Diese Adresse ist nicht erlaubt.": "This address is not allowed.",
    "Adressen im eigenen Netz kann nur ein Admin einbinden.": (
        "Only an admin can add addresses in the local network."
    ),
    "Der Kalender ist nicht erreichbar.": "The calendar cannot be reached.",
    "Der Kalender ist zu groß (höchstens 2 MB).": "The calendar is too large (at most 2 MB).",
    "Zu viele Weiterleitungen.": "Too many redirects.",
    "Das ist keine gültige Kalenderdatei (ICS).": "This is not a valid calendar file (ICS).",
    "Der Kalender enthält zu viele Termine (höchstens 5000).": (
        "The calendar contains too many events (at most 5000)."
    ),
    "Die gespeicherte Adresse lässt sich nicht entschlüsseln.": (
        "The stored address cannot be decrypted."
    ),
    "Dieser Termin kommt aus einem abonnierten Kalender und lässt sich nur dort ändern.": (
        "This event comes from a subscribed calendar and can only be changed there."
    ),
    "Anmeldung am Postfach fehlgeschlagen. Benutzername und Passwort prüfen.": (
        "Signing in to the mailbox failed. Check the user name and password."
    ),
    "Den Ordner gibt es im Postfach nicht.": "The folder does not exist in the mailbox.",
    "Das Postfach antwortet nicht wie erwartet.": "The mailbox does not respond as expected.",
    "Der Mailserver ist nicht erreichbar.": "The mail server cannot be reached.",
    "Das Zertifikat des Mailservers ist ungültig.": "The mail server's certificate is invalid.",
    "Die Verbindung zum Mailserver ist abgebrochen.": (
        "The connection to the mail server was interrupted."
    ),
    "Der Mailserver unterstützt keine verschlüsselte Verbindung (STARTTLS).": (
        "The mail server does not support an encrypted connection (STARTTLS)."
    ),
    "Das gespeicherte Passwort lässt sich nicht entschlüsseln.": (
        "The stored password cannot be decrypted."
    ),
    "Kein offener Terminvorschlag.": "No open appointment suggestion.",
    "Die Anmeldung beim Anbieter ist fehlgeschlagen.": "Signing in with the provider failed.",
    "Die Verbindung zum Anbieter ist abgelaufen. Bitte das Postfach neu verbinden.": (
        "The connection to the provider has expired. Please reconnect the mailbox."
    ),
    "Die Anmeldung bei diesem Anbieter ist auf dem Server nicht eingerichtet.": (
        "Signing in with this provider is not set up on the server."
    ),
    "Google Kalender ist nicht erreichbar.": "Google Calendar cannot be reached.",
    "Google Kalender hat die Anmeldung abgelehnt. Bitte neu verbinden.": (
        "Google Calendar rejected the sign-in. Please reconnect."
    ),
    "Das gespeicherte Token lässt sich nicht entschlüsseln.": (
        "The stored token cannot be decrypted."
    ),
    "Der Outlook-Kalender ist nicht erreichbar.": "The Outlook calendar cannot be reached.",
    "Der Outlook-Kalender hat die Anmeldung abgelehnt. Bitte neu verbinden.": (
        "The Outlook calendar rejected the sign-in. Please reconnect."
    ),
    "Der CalDAV-Kalender ist nicht erreichbar.": "The CalDAV calendar cannot be reached.",
    "Der CalDAV-Server hat die Anmeldung abgelehnt. Benutzername und App-Passwort prüfen.": (
        "The CalDAV server rejected the sign-in. Check the user name and app password."
    ),
    "Der CalDAV-Server antwortet nicht wie erwartet.": (
        "The CalDAV server does not respond as expected."
    ),
    "Unter dieser Adresse wurde kein Kalender gefunden.": "No calendar was found at this address.",
    "Ohne Verschlüsselung (http://) ist CalDAV nur im eigenen Netz erlaubt.": (
        "Without encryption (http://), CalDAV is only allowed in the local network."
    ),
    "Mindestens eine Bedingung angeben.": "Enter at least one condition.",
    "Mindestens eine Aktion wählen.": "Choose at least one action.",
    "Unbekannter Push-Dienst": "Unknown push service",
    "Zu viele Geräte registriert.": "Too many devices registered.",
    "Auf keinem Gerät aktiviert.": "Not enabled on any device.",
    "Ungültige Wiederholung": "Invalid recurrence",
    "Ungültige Wiederholungsregel": "Invalid recurrence rule",
    "Wiederholung braucht FREQ=DAILY|WEEKLY|MONTHLY|YEARLY": (
        "Recurrence needs FREQ=DAILY|WEEKLY|MONTHLY|YEARLY"
    ),
    "FREQ muss DAILY, WEEKLY, MONTHLY oder YEARLY sein": (
        "FREQ must be DAILY, WEEKLY, MONTHLY or YEARLY"
    ),
    "BYDAY ist nur bei wöchentlicher Wiederholung erlaubt": (
        "BYDAY is only allowed for weekly recurrence"
    ),
    "BYDAY enthält ungültige Wochentage": "BYDAY contains invalid weekdays",
    "BYDAY enthält ungültige Tage": "BYDAY contains invalid days",
    "COUNT und UNTIL schließen sich aus": "COUNT and UNTIL are mutually exclusive",
    "WKST ist ungültig": "WKST is invalid",
    "UNTIL muss ein Datum im Format JJJJMMTT sein": "UNTIL must be a date in the format YYYYMMDD",
    "UNTIL muss JJJJMMTT oder JJJJMMTTTHHMMSSZ sein": (
        "UNTIL must be YYYYMMDD or YYYYMMDDTHHMMSSZ"
    ),
}

NOUNS = {
    "Kalender": "calendars",
    "Bereiche": "areas",
    "Kontakte": "contacts",
    "Abo-Links": "subscription links",
    "Passkeys": "passkeys",
    "Postfächer": "mailboxes",
    "Regeln": "rules",
    "Kalenderverbindungen": "calendar connections",
}

Render = Callable[[re.Match[str]], str]

PATTERNS: list[tuple[re.Pattern[str], Render]] = [
    (
        re.compile(r"^Höchstens (\d+) (\S+) möglich\.$"),
        lambda m: f"At most {m[1]} {NOUNS.get(m[2], m[2])} allowed.",
    ),
    (
        re.compile(r"^Zeitraum muss zwischen 1 und (\d+) Tagen liegen\.$"),
        lambda m: f"The period must be between 1 and {m[1]} days.",
    ),
    (
        re.compile(r"^Das Passwort darf höchstens (\d+) Zeichen lang sein\.$"),
        lambda m: f"The password may be at most {m[1]} characters long.",
    ),
    (
        re.compile(r"^Das Passwort muss mindestens (\d+) Zeichen lang sein\.$"),
        lambda m: f"The password must be at least {m[1]} characters long.",
    ),
    (
        re.compile(r"^(INTERVAL|COUNT|BYMONTH|BYMONTHDAY) muss zwischen (\d+) und (\d+) liegen$"),
        lambda m: f"{m[1]} must be between {m[2]} and {m[3]}",
    ),
    (
        re.compile(r"^Nicht unterstützte Wiederholungsregel: (.+)$"),
        lambda m: f"Unsupported recurrence rule: {m[1]}",
    ),
    (re.compile(r"^Nicht unterstützt: (.+)$"), lambda m: f"Not supported: {m[1]}"),
    (
        re.compile(r"^Der Server antwortet mit Status (\d+)\.$"),
        lambda m: f"The server responds with status {m[1]}.",
    ),
]


def language_from(accept_language: str | None) -> Language:
    """Erste unterstützte Sprache aus dem Header, sonst Deutsch."""
    for part in (accept_language or "").split(","):
        tag = part.split(";", 1)[0].strip().lower()
        if tag.startswith("en"):
            return "en"
        if tag.startswith("de"):
            return "de"
    return "de"


def translate(message: str, language: Language) -> str:
    if language != "en":
        return message
    if message in EXACT:
        return EXACT[message]
    for pattern, render in PATTERNS:
        match = pattern.match(message)
        if match:
            return render(match)
    return message
