"""Schnellerfassung: eine Zeile natürliche Sprache (Deutsch) → Aufgabe.

Beispiel::

    parse_quick_add("Rechnung zahlen morgen 14:00 !hoch #finanzen @arbeit", now)
    → Titel „Rechnung zahlen“, morgen 14:00, Priorität hoch, Tag finanzen, Bereich arbeit

Erkannt werden ``#tag``, ``@bereich``, Priorität (``!hoch``/``!mittel``/``!niedrig`` bzw.
``!!!``/``!!``/``!``), Datumsangaben (heute, morgen, übermorgen, Wochentage, „nächste Woche“,
„in 3 Tagen“, „15.10.“, „3. Oktober“, ISO-Datum, Monatsende …), Uhrzeiten („14:00“,
„um 9“, „14 Uhr“, „morgen früh“) und Wiederholungen („täglich“, „jeden Montag“,
„alle 2 Wochen“, „werktags“ …).
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from app.services.recurrence import WEEKDAYS as RRULE_DAYS
from app.services.recurrence import Recurrence

WEEKDAY_NAMES = {
    "montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3, "freitag": 4,
    "samstag": 5, "sonnabend": 5, "sonntag": 6,
}  # fmt: skip
WEEKDAY_ABBREVIATIONS = {"mo": 0, "di": 1, "mi": 2, "do": 3, "fr": 4, "sa": 5, "so": 6}
MONTHS = {
    "januar": 1, "jänner": 1, "jan": 1, "februar": 2, "feb": 2, "märz": 3, "maerz": 3,
    "mär": 3, "mrz": 3, "april": 4, "apr": 4, "mai": 5, "juni": 6, "jun": 6, "juli": 7,
    "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "oktober": 10,
    "okt": 10, "november": 11, "nov": 11, "dezember": 12, "dez": 12,
}  # fmt: skip
NUMBER_WORDS = {
    "ein": 1, "eine": 1, "einen": 1, "einem": 1, "einer": 1, "zwei": 2, "drei": 3, "vier": 4,
    "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12,
}  # fmt: skip
DAYPARTS = {
    "früh": 8, "morgens": 8, "vormittag": 10, "vormittags": 10, "mittag": 12, "mittags": 12,
    "nachmittag": 15, "nachmittags": 15, "abend": 19, "abends": 19, "nacht": 22, "nachts": 22,
}  # fmt: skip
PRIORITY_WORDS = {
    "hoch": 3, "high": 3, "dringend": 3, "wichtig": 3,
    "mittel": 2, "medium": 2, "med": 2,
    "niedrig": 1, "low": 1,
}  # fmt: skip

L = r"(?<![\w])"  # linke Wortgrenze (Unicode-fähig)
R = r"(?![\w])"  # rechte Wortgrenze


def _alternation(words: Iterable[str]) -> str:
    return "|".join(sorted((re.escape(w) for w in words), key=len, reverse=True))


WD = _alternation(WEEKDAY_NAMES)
MONTH = _alternation(MONTHS)
NUM = r"\d{1,3}|" + _alternation(NUMBER_WORDS)
DAYPART = _alternation(DAYPARTS)
PREFIX = r"(?:(?:bis\s+zum|bis\s+zur|bis|am|ab|zum|vom|für|fuer)\s+)?"
TIME_PREFIX = r"(?:(?:um|ab|gegen|bis)\s+)?"
HOUR = r"([01]?\d|2[0-3])"
MINUTE = r"([0-5]\d)"

STOPWORDS = {"am", "um", "bis", "ab", "zum", "zur", "vom", "gegen", "und", "für", "fuer", "in"}


@dataclass
class QuickAddResult:
    title: str
    due_date: date | None = None
    due_time: time | None = None
    priority: int = 0
    tags: list[str] = field(default_factory=list)
    area: str | None = None
    recurrence: str | None = None
    tokens: list[str] = field(default_factory=list)


def _number(text: str) -> int:
    text = text.lower()
    return int(text) if text.isdigit() else NUMBER_WORDS[text]


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def _next_weekday(today: date, weekday: int, *, include_today: bool = False) -> date:
    delta = (weekday - today.weekday()) % 7
    if delta == 0 and not include_today:
        delta = 7
    return today + timedelta(days=delta)


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


class _Parser:
    def __init__(self, text: str, now: datetime) -> None:
        self.text = " " + text.strip() + " "
        self.now = now
        self.today = now.date()
        self.result = QuickAddResult(title="")

    def take(
        self, pattern: str, handler: Callable[[re.Match[str]], bool], *, repeat: bool = False
    ) -> None:
        """Sucht ``pattern``; wenn ``handler`` zustimmt, wird der Treffer aus dem Text entfernt."""
        regex = re.compile(pattern, re.IGNORECASE)
        position = 0
        while True:
            match = regex.search(self.text, position)
            if match is None:
                return
            if handler(match):
                self.result.tokens.append(match.group(0).strip())
                self.text = self.text[: match.start()] + " " + self.text[match.end() :]
                if not repeat:
                    return
                position = match.start()
            else:
                position = match.end()

    # --- Handler -------------------------------------------------------------

    def _tag(self, m: re.Match[str]) -> bool:
        tag = m.group(1).lower()
        if tag not in self.result.tags and len(self.result.tags) < 20:
            self.result.tags.append(tag)
        return True

    def _area(self, m: re.Match[str]) -> bool:
        self.result.area = m.group(1)
        return True

    def _priority_word(self, m: re.Match[str]) -> bool:
        self.result.priority = PRIORITY_WORDS[m.group(1).lower()]
        return True

    def _priority_marks(self, m: re.Match[str]) -> bool:
        self.result.priority = len(m.group(1))
        return True

    def _set_date(self, value: date | None) -> bool:
        if value is None or self.result.due_date is not None:
            return False
        self.result.due_date = value
        return True

    def _set_time(self, hour: int, minute: int = 0) -> bool:
        if self.result.due_time is not None:
            return False
        self.result.due_time = time(hour, minute)
        return True

    def _set_recurrence(self, rule: Recurrence) -> bool:
        if self.result.recurrence is not None:
            return False
        self.result.recurrence = rule.to_rrule()
        self._rule = rule
        return True

    def _date_handler(self, value: date) -> Callable[[re.Match[str]], bool]:
        return lambda _match: self._set_date(value)

    def _recurrence_handler(self, rule: Recurrence) -> Callable[[re.Match[str]], bool]:
        return lambda _match: self._set_recurrence(rule)

    # --- Ablauf --------------------------------------------------------------

    def parse(self) -> QuickAddResult:
        self.take(r"(?<!\S)#(\w[\w-]{0,39})(?!\S)", self._tag, repeat=True)
        self.take(r"(?<!\S)@(\w[\w-]{0,59})(?!\S)", self._area)
        self.take(r"(?<!\S)!(" + _alternation(PRIORITY_WORDS) + r")(?!\S)", self._priority_word)
        self.take(r"(?<!\S)(!{1,3})(?!\S)", self._priority_marks)
        self._recurrences()
        self._day_with_daypart()
        self._relative_dates()
        self._named_dates()
        self._absolute_dates()
        self._times()
        self._finish()
        return self.result

    def _recurrences(self) -> None:
        simple = {
            r"täglich|taeglich|jeden\s+tag|alle\s+tage": Recurrence("DAILY"),
            r"werktags|jeden\s+werktag|an\s+werktagen": Recurrence("WEEKLY", byday=RRULE_DAYS[:5]),
            r"zweiwöchentlich|zweiwoechentlich|14-tägig|vierzehntägig": Recurrence("WEEKLY", 2),
            r"wöchentlich|woechentlich|jede\s+woche": Recurrence("WEEKLY"),
            r"monatlich|jeden\s+monat": Recurrence("MONTHLY"),
            r"jährlich|jaehrlich|jedes\s+jahr": Recurrence("YEARLY"),
        }
        for pattern, rule in simple.items():
            self.take(L + r"(?:" + pattern + r")" + R, self._recurrence_handler(rule))

        units = {"tag": "DAILY", "woche": "WEEKLY", "monat": "MONTHLY", "jahr": "YEARLY"}

        def every_n(m: re.Match[str]) -> bool:
            interval = _number(m.group(1))
            unit = m.group(2).lower()
            freq = next(v for k, v in units.items() if unit.startswith(k))
            return 1 <= interval <= 365 and self._set_recurrence(Recurrence(freq, interval))

        self.take(L + r"alle\s+(" + NUM + r")\s+(tage|wochen|monate|jahre)" + R, every_n)

        def weekdays_in(text: str) -> tuple[str, ...]:
            found = {WEEKDAY_NAMES[w.lower()] for w in re.findall(WD, text, re.IGNORECASE)}
            return tuple(RRULE_DAYS[i] for i in sorted(found))

        list_sep = r"(?:\s*,\s*|\s+und\s+)"
        self.take(
            L + r"jeden\s+(?:" + WD + r")(?:" + list_sep + r"(?:" + WD + r"))*" + R,
            lambda m: self._set_recurrence(Recurrence("WEEKLY", byday=weekdays_in(m.group(0)))),
        )
        self.take(
            L + r"(?:" + WD + r")s(?:" + list_sep + r"(?:" + WD + r")s)*" + R,
            lambda m: self._set_recurrence(Recurrence("WEEKLY", byday=weekdays_in(m.group(0)))),
        )

    def _day_value(self, word: str) -> date:
        word = word.lower()
        if word == "heute":
            return self.today
        if word == "morgen":
            return self.today + timedelta(days=1)
        if word in ("übermorgen", "uebermorgen"):
            return self.today + timedelta(days=2)
        return _next_weekday(self.today, WEEKDAY_NAMES[word])

    def _day_with_daypart(self) -> None:
        def handler(m: re.Match[str]) -> bool:
            day, part = m.group(1).lower(), m.group(2).lower()
            if day == "morgen" and part in ("morgen", "morgens"):
                return False
            hour = 8 if part == "morgen" else DAYPARTS[part]
            return self._set_date(self._day_value(day)) and self._set_time(hour)

        days = r"heute|morgen|übermorgen|uebermorgen|" + WD
        self.take(PREFIX + L + r"(" + days + r")\s+(" + DAYPART + r"|morgen)" + R, handler)

    def _relative_dates(self) -> None:
        def handler(m: re.Match[str]) -> bool:
            amount = _number(m.group(1))
            unit = m.group(2).lower()
            if unit.startswith("tag"):
                value = self.today + timedelta(days=amount)
            elif unit.startswith("woche"):
                value = self.today + timedelta(weeks=amount)
            elif unit.startswith("monat"):
                value = _add_months(self.today, amount)
            else:
                value = _add_months(self.today, 12 * amount)
            return self._set_date(value)

        self.take(
            L + r"in\s+(" + NUM + r")\s+(tagen|tag|wochen|woche|monaten|monat|jahren|jahr)" + R,
            handler,
        )

    def _named_dates(self) -> None:
        today = self.today
        weekday = today.weekday()
        month_end = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        next_monday = today + timedelta(days=7 - weekday)
        weekend = today if weekday >= 5 else today + timedelta(days=5 - weekday)
        end_of_week = (
            today + timedelta(days=(4 - weekday) % 7)
            if weekday <= 4
            else (today + timedelta(days=11 - weekday))
        )
        fixed = {
            r"übermorgen|uebermorgen": today + timedelta(days=2),
            r"morgen": today + timedelta(days=1),
            r"heute": today,
            r"übernächste\s+woche|uebernaechste\s+woche": next_monday + timedelta(days=7),
            r"(?:nächste|naechste|kommende)\s+woche": next_monday,
            r"(?:am\s+)?wochenende": weekend,
            r"ende\s+der\s+woche": end_of_week,
            r"(?:am\s+)?monatsende|ende\s+des\s+monats|ende\s+monat": month_end,
            r"(?:nächsten|naechsten|kommenden)\s+monat": _add_months(today.replace(day=1), 1),
        }
        for pattern, value in fixed.items():
            self.take(PREFIX + L + r"(?:" + pattern + r")" + R, self._date_handler(value))

        qualifier = r"(?:(?:nächsten|naechsten|nächster|kommenden|diesen)\s+)?"
        self.take(
            PREFIX + qualifier + L + r"(" + WD + r")" + R,
            lambda m: self._set_date(_next_weekday(today, WEEKDAY_NAMES[m.group(1).lower()])),
        )
        abbreviations = _alternation(WEEKDAY_ABBREVIATIONS)
        self.take(
            PREFIX + L + r"(" + abbreviations + r")\.(?!\d)",
            lambda m: self._set_date(
                _next_weekday(today, WEEKDAY_ABBREVIATIONS[m.group(1).lower()])
            ),
        )

    def _with_year(self, day: int, month: int, year: int | None) -> date | None:
        if year is not None:
            if year < 100:
                year += 2000
            return _safe_date(year, month, day)
        value = _safe_date(self.today.year, month, day)
        if value is not None and value < self.today:
            value = _safe_date(self.today.year + 1, month, day)
        return value

    def _absolute_dates(self) -> None:
        self.take(
            PREFIX + L + r"(\d{4})-(\d{2})-(\d{2})" + R,
            lambda m: self._set_date(_safe_date(int(m[1]), int(m[2]), int(m[3]))),
        )
        self.take(
            PREFIX + L + r"(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})?(?![\d])",
            lambda m: self._set_date(
                self._with_year(int(m[1]), int(m[2]), int(m[3]) if m[3] else None)
            ),
        )
        self.take(
            PREFIX + L + r"(\d{1,2})\.?\s*(" + MONTH + r")\.?(?:\s+(\d{4}))?" + R,
            lambda m: self._set_date(
                self._with_year(int(m[1]), MONTHS[m[2].lower()], int(m[3]) if m[3] else None)
            ),
        )

    def _times(self) -> None:
        def hm(m: re.Match[str]) -> bool:
            return self._set_time(
                int(m[1]), int(m[2]) if m.lastindex and m.lastindex >= 2 and m[2] else 0
            )

        self.take(L + TIME_PREFIX + HOUR + r":" + MINUTE + r"(?:\s*uhr)?" + R, hm)
        self.take(L + TIME_PREFIX + HOUR + r"\." + MINUTE + r"\s*uhr" + R, hm)
        self.take(L + TIME_PREFIX + HOUR + r"\s*uhr" + R, hm)
        self.take(L + r"(?:um|gegen)\s+" + HOUR + r"(?:\." + MINUTE + r")?" + R, hm)

    def _finish(self) -> None:
        result = self.result
        rule: Recurrence | None = getattr(self, "_rule", None)
        if result.due_date is None and rule is not None:
            first = rule.first_on_or_after(self.today)
            if (
                first == self.today
                and result.due_time is not None
                and datetime.combine(self.today, result.due_time) <= self.now
            ):
                first = rule.first_on_or_after(self.today + timedelta(days=1))
            result.due_date = first
        if result.due_date is None and result.due_time is not None:
            candidate = datetime.combine(self.today, result.due_time)
            result.due_date = self.today if candidate > self.now else self.today + timedelta(days=1)

        words = self.text.split()
        while words and words[0].lower().strip(",;:") in STOPWORDS:
            words.pop(0)
        while words and words[-1].lower().strip(",;:") in STOPWORDS:
            words.pop()
        title = " ".join(words).strip(" ,;:-–")
        result.title = re.sub(r"\s+([,;:.!?])", r"\1", title)


def parse_quick_add(text: str, now: datetime) -> QuickAddResult:
    """``now`` ist die lokale Zeit des Nutzers (ohne Zeitzone)."""
    result = _Parser(text[:500], now.replace(tzinfo=None)).parse()
    if not result.title:
        result.title = text.strip()[:300]
    result.title = result.title[:300]
    return result
