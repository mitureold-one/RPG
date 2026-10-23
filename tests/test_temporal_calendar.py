"""Testes unitários para temporal/calendar.py."""

from __future__ import annotations

import unittest
from pathlib import Path

from campaign.locator import parse_regras_manifest
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

        # Calendar aware
        cal = {"months": ["M1", "M2"], "days_per_month": [30, 30]}
        self.assertEqual(parse_time_increment("+1y", calendar=cal), 60 * 1440)
        self.assertEqual(parse_time_increment("+1mo", calendar=cal), 30 * 1440)

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

    def test_advance_valiria_calendar_year(self) -> None:
        manifest = parse_regras_manifest(Path("tests/fixtures/campaigns/imperio_valiria/regras.md"))
        cal = manifest["calendar"]
        # +1y no calendário de 360 dias não deve ter drift de 5 dias
        res = advance_time_str("05 de Ventania de 304, 08:06", "+1y", calendar=cal)
        self.assertEqual(res, "5 de Ventania de 305, 08:06")

        # +1y por minutos também respeita 360 dias quando calendar é informado
        mins_year = parse_time_increment("+1y", calendar=cal)
        self.assertEqual(mins_year, 360 * 1440)
        res_mins = advance_time_str("05 de Ventania de 304, 08:06", mins_year, calendar=cal)
        self.assertEqual(res_mins, "5 de Ventania de 305, 08:06")

        # 2 anos exatos sem drift
        res_2y = advance_time_str("05 de Ventania de 304, 08:06", "+2y", calendar=cal)
        self.assertEqual(res_2y, "5 de Ventania de 306, 08:06")

    def test_advance_valiria_calendar_month(self) -> None:
        manifest = parse_regras_manifest(Path("tests/fixtures/campaigns/imperio_valiria/regras.md"))
        cal = manifest["calendar"]
        # +1mo de 30 de Ventania cai no 30 do próximo mês (Geada)
        res = advance_time_str("30 de Ventania de 304, 08:06", "+1mo", calendar=cal)
        self.assertEqual(res, "30 de Geada de 304, 08:06")

    def test_advance_gregorian_month_clamped(self) -> None:
        # 31 de Janeiro +1mo deve cair em 28 de Fevereiro em ano não bissexto (2026)
        res = advance_time_str("31 de Janeiro de 2026, 12:00", "+1mo")
        self.assertEqual(res, "28 de Fevereiro de 2026, 12:00")


if __name__ == "__main__":
    unittest.main()
