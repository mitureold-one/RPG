"""Tempo de jogo: incrementos relativos, calendários declarativos e avanço de datas.

Sem I/O. O bloco ``calendar:`` chega já lido de ``regras.md`` pela camada de campanha.
"""

import datetime
import re

MONTHS_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

MONTHS_MAP = {
    "janeiro": 1, "jan": 1,
    "fevereiro": 2, "fev": 2,
    "março": 3, "marco": 3, "mar": 3,
    "abril": 4, "abr": 4,
    "maio": 5, "mai": 5,
    "junho": 6, "jun": 6,
    "julho": 7, "jul": 7,
    "agosto": 8, "ago": 8,
    "setembro": 9, "set": 9,
    "outubro": 10, "out": 10,
    "novembro": 11, "nov": 11,
    "dezembro": 12, "dez": 12,
}


def _normalize_calendar(raw) -> dict:
    """Normaliza o bloco ``calendar:`` do manifesto de regras.md.

    Formato aceito::

        calendar:
          months: ["Ventania", "Geada", "..."]
          days_per_month: 30          # int ou lista alinhada a months
    """
    if not isinstance(raw, dict):
        return {}
    raw_months = raw.get("months")
    if not isinstance(raw_months, list):
        return {}
    months = [str(m).strip() for m in raw_months if str(m).strip()]
    if not months:
        return {}

    raw_days = raw.get("days_per_month", 30)
    if isinstance(raw_days, int):
        days = [max(1, raw_days)] * len(months)
    elif isinstance(raw_days, list):
        days = []
        for value in raw_days[: len(months)]:
            try:
                days.append(max(1, int(value)))
            except (TypeError, ValueError):
                days.append(30)
        days.extend([30] * (len(months) - len(days)))
    else:
        days = [30] * len(months)
    return {"months": months, "days_per_month": days}


def parse_time_increment(val_str: str) -> int:
    """Converte incrementos como '+60d', '+2mo', '+1y', '+2h' e '+30m' em minutos.

    ``m`` é sempre minuto; meses usam ``mo``/``mes``/``meses``.
    """
    clean = val_str.strip().lstrip("+").lower()
    m = re.match(r"^(\d+)\s*([a-zçã]+)?$", clean)
    if not m:
        return 0
    num = int(m.group(1))
    unit = (m.group(2) or "m").lower()
    if unit in ("m", "min", "mins", "minuto", "minutos"):
        return num
    elif unit in ("h", "hr", "hrs", "hora", "horas"):
        return num * 60
    elif unit in ("d", "dia", "dias"):
        return num * 1440
    elif unit in ("w", "sem", "semana", "semanas"):
        return num * 1440 * 7
    elif unit in ("mo", "mes", "mês", "meses"):
        return num * 1440 * 30
    elif unit in ("y", "a", "ano", "anos"):
        return num * 1440 * 365
    return num


def advance_time_str(dt_str: str, minutes: int, calendar: dict | None = None) -> str:
    """Avança data e hora respeitando dias, meses, anos ou horários simples.

    ``calendar`` é o bloco opcional ``calendar:`` de ``regras.md`` com
    ``months`` e ``days_per_month``. Sem calendário, aceita meses gregorianos
    e anos de 1 a 4 dígitos. Datas com mês desconhecido levantam ``ValueError``
    em vez de serem convertidas silenciosamente para Janeiro.
    """
    if minutes == 0:
        return dt_str

    cal = calendar or {}
    months = cal.get("months") or []
    days_per_month = cal.get("days_per_month") or []

    # Padrão A: 'DD de Mês de YYYY, HH:MM' ou 'DD de Mês de YYYY'
    m_full = re.search(
        r"(\d{1,2})\s+de\s+([A-Za-zçÇãÃõÕéÉêÊíÍóÓúÚ]+)\s+de\s+(\d{1,4})(?:,\s*(\d{1,2}):(\d{2}))?",
        dt_str,
        re.IGNORECASE,
    )
    if m_full:
        day = int(m_full.group(1))
        m_name = m_full.group(2)
        year = int(m_full.group(3))
        h = int(m_full.group(4)) if m_full.group(4) else 12
        mins = int(m_full.group(5)) if m_full.group(5) else 0
        has_time = bool(m_full.group(4))

        if months:
            month_idx = next(
                (i for i, name in enumerate(months) if name.casefold() == m_name.casefold()),
                None,
            )
            if month_idx is None:
                raise ValueError(
                    f"Mês '{m_name}' não consta no calendário da campanha. "
                    f"Declare 'calendar.months' em regras.md."
                )
            total = h * 60 + mins + minutes
            day_delta = total // 1440
            rem = total % 1440
            new_day = day + day_delta
            new_idx = month_idx
            if isinstance(days_per_month, int):
                days = [max(1, days_per_month)] * len(months)
            else:
                days = list(days_per_month or [])
                if len(days) < len(months):
                    days.extend([30] * (len(months) - len(days)))
            while new_day > days[new_idx]:
                new_day -= days[new_idx]
                new_idx += 1
                if new_idx >= len(months):
                    new_idx = 0
                    year += 1
            new_h, new_m = divmod(rem, 60)
            formatted = f"{new_day} de {months[new_idx]} de {year}"
            if has_time:
                formatted += f", {new_h:02d}:{new_m:02d}"
            return dt_str[:m_full.start()] + formatted + dt_str[m_full.end():]

        month_num = MONTHS_MAP.get(m_name.lower())
        if not month_num:
            # Fallback conservador para calendários diegéticos ainda não
            # declarados: permite avanços que permaneçam no mesmo mês (30 dias)
            # sem inventar nomes de meses vizinhos. Qualquer travessia de mês
            # exige o bloco calendar em regras.md.
            total = h * 60 + mins + minutes
            day_delta = total // 1440
            rem = total % 1440
            new_day = day + day_delta
            if 1 <= new_day <= 30:
                new_h, new_m = divmod(rem, 60)
                formatted = f"{new_day} de {m_name} de {year}"
                if has_time:
                    formatted += f", {new_h:02d}:{new_m:02d}"
                return dt_str[:m_full.start()] + formatted + dt_str[m_full.end():]
            raise ValueError(
                f"Mês '{m_name}' não é gregoriano e o avanço ultrapassa o mês. "
                f"Declare 'calendar.months' em regras.md para atravessar meses."
            )
        try:
            cur_dt = datetime.datetime(year, month_num, day, h, mins)
        except ValueError as exc:
            raise ValueError(f"Data inválida '{dt_str}': {exc}") from exc
        new_dt = cur_dt + datetime.timedelta(minutes=minutes)
        new_month_name = MONTHS_PT[new_dt.month]
        if has_time:
            formatted = f"{new_dt.day} de {new_month_name} de {new_dt.year}, {new_dt.hour:02d}:{new_dt.minute:02d}"
        else:
            formatted = f"{new_dt.day} de {new_month_name} de {new_dt.year}"
        return dt_str[:m_full.start()] + formatted + dt_str[m_full.end():]

    # Padrão B: 'DD/MM/YYYY, HH:MM'
    m_slash = re.search(r"(\d{1,2})/(\d{1,2})/(\d{1,4})(?:,\s*(\d{1,2}):(\d{2}))?", dt_str)
    if m_slash:
        day, month, year = int(m_slash.group(1)), int(m_slash.group(2)), int(m_slash.group(3))
        h = int(m_slash.group(4)) if m_slash.group(4) else 12
        mins = int(m_slash.group(5)) if m_slash.group(5) else 0
        has_time = bool(m_slash.group(4))
        try:
            cur_dt = datetime.datetime(year, month, day, h, mins)
        except ValueError as exc:
            raise ValueError(f"Data inválida '{dt_str}': {exc}") from exc
        new_dt = cur_dt + datetime.timedelta(minutes=minutes)
        if has_time:
            formatted = f"{new_dt.day:02d}/{new_dt.month:02d}/{new_dt.year}, {new_dt.hour:02d}:{new_dt.minute:02d}"
        else:
            formatted = f"{new_dt.day:02d}/{new_dt.month:02d}/{new_dt.year}"
        return dt_str[:m_slash.start()] + formatted + dt_str[m_slash.end():]

    # Padrão C: 'Dia X, HH:MM'
    m_dia = re.search(r"Dia\s+(\d+)(?:,\s*(\d{1,2}):(\d{2}))?", dt_str, re.IGNORECASE)
    if m_dia:
        day_num = int(m_dia.group(1))
        h = int(m_dia.group(2)) if m_dia.group(2) else 12
        mins = int(m_dia.group(3)) if m_dia.group(3) else 0
        total_mins = h * 60 + mins + minutes
        days_added = total_mins // 1440
        rem_mins = total_mins % 1440
        new_day = day_num + days_added
        new_h = rem_mins // 60
        new_m = rem_mins % 60
        has_time = bool(m_dia.group(2))
        if has_time:
            formatted = f"Dia {new_day}, {new_h:02d}:{new_m:02d}"
        else:
            formatted = f"Dia {new_day}"
        return dt_str[:m_dia.start()] + formatted + dt_str[m_dia.end():]

    # Fallback D: apenas HH:MM (sem data; não inventa dia)
    m_time = re.search(r"(\d{1,2}):(\d{2})", dt_str)
    if m_time:
        h, mins = int(m_time.group(1)), int(m_time.group(2))
        total = h * 60 + mins + minutes
        new_h = (total // 60) % 24
        new_m = total % 60
        return dt_str[:m_time.start()] + f"{new_h:02d}:{new_m:02d}" + dt_str[m_time.end():]

    raise ValueError(
        f"Formato de data não reconhecido: '{dt_str}'. Use 'DD de Mês de YYYY, HH:MM', "
        f"'DD/MM/YYYY, HH:MM', 'Dia X, HH:MM' ou configure 'calendar' em regras.md."
    )
