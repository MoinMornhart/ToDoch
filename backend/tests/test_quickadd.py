from datetime import date, datetime, time

import pytest

from app.quickadd import parse_quick_add

# Freitag, 11. September 2026, 10:00 Uhr
NOW = datetime(2026, 9, 11, 10, 0)


def parse(text: str):  # type: ignore[no-untyped-def]
    return parse_quick_add(text, NOW)


def test_full_example() -> None:
    r = parse("Rechnung zahlen morgen 14:00 !hoch #finanzen @arbeit")
    assert r.title == "Rechnung zahlen"
    assert r.due_date == date(2026, 9, 12)
    assert r.due_time == time(14, 0)
    assert r.priority == 3
    assert r.tags == ["finanzen"]
    assert r.area == "arbeit"


@pytest.mark.parametrize(
    ("text", "title", "due", "at"),
    [
        ("Zahnarzt am 15.10. um 9 Uhr anrufen", "Zahnarzt anrufen", date(2026, 10, 15), time(9)),
        ("Steuererklärung bis zum 31.07.2027", "Steuererklärung", date(2027, 7, 31), None),
        ("Meeting 3. Oktober 10:30", "Meeting", date(2026, 10, 3), time(10, 30)),
        ("Meeting am 3. Okt. 2027", "Meeting", date(2027, 10, 3), None),
        ("Bericht Montag", "Bericht", date(2026, 9, 14), None),
        ("Sport nächsten Freitag", "Sport", date(2026, 9, 18), None),
        ("Treffen Mo. 14 Uhr", "Treffen", date(2026, 9, 14), time(14)),
        ("Anruf in 2 Wochen", "Anruf", date(2026, 9, 25), None),
        ("Abgabe in einem Monat", "Abgabe", date(2026, 10, 11), None),
        ("Paket in 3 Tagen abholen", "Paket abholen", date(2026, 9, 14), None),
        ("Einkaufen heute abend", "Einkaufen", date(2026, 9, 11), time(19)),
        ("Joggen morgen früh", "Joggen", date(2026, 9, 12), time(8)),
        ("Anruf übermorgen nachmittags", "Anruf", date(2026, 9, 13), time(15)),
        ("Miete zahlen Monatsende", "Miete zahlen", date(2026, 9, 30), None),
        ("Planung nächste Woche", "Planung", date(2026, 9, 14), None),
        ("Ausflug am Wochenende", "Ausflug", date(2026, 9, 12), None),
        ("Termin 2026-12-24", "Termin", date(2026, 12, 24), None),
        ("Geburtstag Oma 5.3.", "Geburtstag Oma", date(2027, 3, 5), None),
        ("Anrufen 16 Uhr", "Anrufen", date(2026, 9, 11), time(16)),
        ("Anrufen 8 Uhr", "Anrufen", date(2026, 9, 12), time(8)),
        ("Zug um 7.45 Uhr", "Zug", date(2026, 9, 12), time(7, 45)),
        ("Probe am 12.9. um 14:30", "Probe", date(2026, 9, 12), time(14, 30)),
        ("Heute Wäsche", "Wäsche", date(2026, 9, 11), None),
    ],
)
def test_dates_and_times(text: str, title: str, due: date, at: time | None) -> None:
    r = parse(text)
    assert r.title == title
    assert r.due_date == due
    assert r.due_time == at


@pytest.mark.parametrize(
    ("text", "title", "rule", "due"),
    [
        (
            "Müll rausbringen jeden Dienstag",
            "Müll rausbringen",
            "FREQ=WEEKLY;BYDAY=TU",
            date(2026, 9, 15),
        ),
        ("Blumen gießen alle 3 Tage", "Blumen gießen", "FREQ=DAILY;INTERVAL=3", date(2026, 9, 11)),
        ("Gym montags und donnerstags", "Gym", "FREQ=WEEKLY;BYDAY=MO,TH", date(2026, 9, 14)),
        ("Standup werktags", "Standup", "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", date(2026, 9, 11)),
        ("Bericht täglich", "Bericht", "FREQ=DAILY", date(2026, 9, 11)),
        ("Zeitung wöchentlich", "Zeitung", "FREQ=WEEKLY", date(2026, 9, 11)),
        ("Abrechnung monatlich", "Abrechnung", "FREQ=MONTHLY", date(2026, 9, 11)),
        ("Putzplan alle zwei Wochen", "Putzplan", "FREQ=WEEKLY;INTERVAL=2", date(2026, 9, 11)),
        (
            "Jour fixe jeden Montag, Mittwoch",
            "Jour fixe",
            "FREQ=WEEKLY;BYDAY=MO,WE",
            date(2026, 9, 14),
        ),
    ],
)
def test_recurrence(text: str, title: str, rule: str, due: date) -> None:
    r = parse(text)
    assert r.title == title
    assert r.recurrence == rule
    assert r.due_date == due


def test_recurrence_with_explicit_date_and_time() -> None:
    r = parse("Standup werktags 9:15")
    assert r.recurrence == "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
    assert r.due_time == time(9, 15)
    # 9:15 ist heute (Freitag) schon vorbei → nächster Werktag ist Montag
    assert r.due_date == date(2026, 9, 14)


@pytest.mark.parametrize(
    ("text", "priority"),
    [("A !!!", 3), ("A !!", 2), ("A !", 1), ("A !niedrig", 1), ("A !mittel", 2), ("A", 0)],
)
def test_priority(text: str, priority: int) -> None:
    r = parse(text)
    assert r.priority == priority
    assert r.title == "A"


def test_exclamation_inside_word_is_kept() -> None:
    r = parse("Wichtig!")
    assert r.title == "Wichtig!"
    assert r.priority == 0


def test_tags_are_deduplicated_and_lowercased() -> None:
    r = parse("Projekt #Arbeit #kunde-x #arbeit")
    assert r.tags == ["arbeit", "kunde-x"]
    assert r.title == "Projekt"


def test_invalid_date_is_left_in_title() -> None:
    r = parse("Test 30.02.")
    assert r.due_date is None
    assert r.title == "Test 30.02."


def test_plain_text() -> None:
    r = parse("Nur ein ganz normaler Satz")
    assert r.title == "Nur ein ganz normaler Satz"
    assert r.due_date is None and r.due_time is None and r.recurrence is None


def test_morgens_is_not_tomorrow() -> None:
    r = parse("morgens Tabletten nehmen")
    assert r.due_date is None
    assert r.title == "morgens Tabletten nehmen"


def test_title_falls_back_to_text() -> None:
    r = parse("morgen")
    assert r.title == "morgen"
    assert r.due_date == date(2026, 9, 12)


def test_long_input_is_truncated() -> None:
    r = parse("x" * 2000)
    assert len(r.title) <= 300
