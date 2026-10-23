"""Testes unitários para temporal/calendar.py."""

from __future__ import annotations

import unittest

from temporal.calendar import (
    MONTHS_MAP,
    MONTHS_PT,
    _normalize_calendar,
    advance_time_str,
    parse_time_increment,
)


class TemporalCalendarTests(unittest.TestCase):
    def test_parse_time_increment(self) -> None:
        self.assertEqual(parse_time_increment("+15m"), 15)
        self.assertEqual(parse_time_increment("+2h"), 120)
        self.assertEqual(parse_time_increment("+1d"), 1440)
        self.assertEqual(parse_time_increment("+2w"), 20160)
        self.assertEqual(parse_time_increment("+1mo"), 43200)
        self.assertEqual(parse_time_increment("+1y"), 525600)
        self.assertEqual(parse_time_increment("inválido"), 0)

    def test_normalize_calendar(self) -> None:
        # None or invalid input
        self.assertEqual(_normalize_calendar(None), {})
        self.assertEqual(_normalize_calendar({}), {})

        # Valid input with single int days
        cal = _normalize_calendar({"months": ["M1", "M2"], "days_per_month": 28})
        self.assertEqual(cal["months"], ["M1", "M2"])
        self.assertEqual(cal["days_per_month"], [28, 28])

        # Valid input with list days
        cal2 = _normalize_calendar({"months": ["M1", "M2"], "days_per_month": [30, 25]})
        self.assertEqual(cal2["days_per_month"], [30, 25])

    def test_advance_gregorian_time(self) -> None:
        res = advance_time_str("10 de Outubro de 2026, 12:00", 60)
        self.assertEqual(res, "10 de Outubro de 2026, 13:00")

        res_day = advance_time_str("10 de Outubro de 2026, 12:00", 1440)
        self.assertEqual(res_day, "11 de Outubro de 2026, 12:00")

    def test_advance_custom_calendar(self) -> None:
        cal = {"months": ["Ventania", "Geada"], "days_per_month": [30, 30]}
        res = advance_time_str("29 de Ventania de 304, 12:00", 2880, calendar=cal)
        self.assertEqual(res, "1 de Geada de 304, 12:00")


if __name__ == "__main__":
    unittest.main()
