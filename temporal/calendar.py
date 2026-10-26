"""Tempo de jogo: incrementos relativos, calendários declarativos e avanço de datas.

Sem I/O. O bloco ``calendar:`` chega já lido de ``regras.md`` pela camada de campanha.
"""

import calendar as _py_cal
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


def parse_time_increment(val_str: str, calendar: dict | None = None) -> int:
    """Converte incrementos como '+60d', '+2mo', '+1y', '+2h' e '+30m' em minutos.

    ``m`` é sempre minuto; meses usam ``mo``/``mes``/``meses``.
    Se ``calendar`` for informado, respeita a duração do ano/mês do calendário declarado.
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
        if calendar:
            cal = _normalize_calendar(calendar)
            days = cal.get("days_per_month")
            if days:
                return num * 1440 * (sum(days) // len(days))
        return num * 1440 * 30
    elif unit in ("y", "a", "ano", "anos"):
        if calendar:
            cal = _normalize_calendar(calendar)
            days = cal.get("days_per_month")
            if days:
                return num * 1440 * sum(days)
        return num * 1440 * 365
    return num


def advance_time_str(dt_str: str, advance: int | str, calendar: dict | None = None) -> str:
    """Avança data e hora respeitando dias, meses, anos ou horários simples.

    ``advance`` pode ser minutos (int) ou string de incremento relativo (ex: '+1y', '+2mo', '+30m').
    ``calendar`` é o bloco opcional ``calendar:`` de ``regras.md`` com
    ``months`` e ``days_per_month``. Sem calendário, aceita meses gregorianos
    e anos de 1 a 4 dígitos. Datas com mês desconhecido levantam ``ValueError``
    em vez de serem convertidas silenciosamente para Janeiro.
    """
    if advance == 0 or advance == "":
        return dt_str

    cal = _normalize_calendar(calendar) if calendar else {}
    months = cal.get("months") or []
    days_per_month = cal.get("days_per_month") or []

    if isinstance(advance, str):
        clean_adv = advance.strip().lstrip("+").lower()
        m_adv = re.match(r"^(\d+)\s*([a-zçã]+)?$", clean_adv)
        if not m_adv:
            raise ValueError(
                f"Incremento de tempo inválido: '{advance}'. Use '+30m', '+6h', '+14d', '+2mo' ou '+1y'."
            )
        adv_num = int(m_adv.group(1))
        adv_unit = (m_adv.group(2) or "m").lower()
        if adv_num <= 0:
            return dt_str

        is_year = adv_unit in ("y", "a", "ano", "anos")
        is_month = adv_unit in ("mo", "mes", "mês", "meses")

        if is_year or is_month:
            # Padrão A: 'DD de Mês de YYYY, HH:MM' ou 'DD de Mês de YYYY'
            m_full = re.search(
                r"(\d{1,2})\s+de\s+([A-Za-zçÇãÃõÕéÉêÊíÍóÓúÚ\-]+)\s+de\s+(\d{1,4})(?:,\s*(\d{1,2}):(\d{2}))?",
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
                    if is_year:
                        new_year = year + adv_num
                        new_idx = month_idx
                        new_day = min(day, days_per_month[new_idx])
                    else:  # is_month
                        total_idx = month_idx + adv_num
                        year_delta, new_idx = divmod(total_idx, len(months))
                        new_year = year + year_delta
                        new_day = min(day, days_per_month[new_idx])

                    formatted = f"{new_day} de {months[new_idx]} de {new_year}"
                    if has_time:
                        formatted += f", {h:02d}:{mins:02d}"
                    return dt_str[:m_full.start()] + formatted + dt_str[m_full.end():]

                month_num = MONTHS_MAP.get(m_name.lower())
                if not month_num:
                    raise ValueError(
                        f"Mês '{m_name}' não é gregoriano e o avanço ultrapassa o mês. "
                        f"Declare 'calendar.months' em regras.md para atravessar meses."
                    )
                if is_year:
                    new_year = year + adv_num
                    max_d = _py_cal.monthrange(new_year, month_num)[1]
                    new_day = min(day, max_d)
                    new_m_num = month_num
                else:  # is_month
                    total_m = (month_num - 1) + adv_num
                    year_delta, m_zero = divmod(total_m, 12)
                    new_year = year + year_delta
                    new_m_num = m_zero + 1
                    max_d = _py_cal.monthrange(new_year, new_m_num)[1]
                    new_day = min(day, max_d)

                new_m_name = MONTHS_PT[new_m_num]
                formatted = f"{new_day} de {new_m_name} de {new_year}"
                if has_time:
                    formatted += f", {h:02d}:{mins:02d}"
                return dt_str[:m_full.start()] + formatted + dt_str[m_full.end():]

            # Padrão B: 'DD/MM/YYYY, HH:MM'
            m_slash = re.search(r"(\d{1,2})/(\d{1,2})/(\d{1,4})(?:,\s*(\d{1,2}):(\d{2}))?", dt_str)
            if m_slash:
                day, month, year = int(m_slash.group(1)), int(m_slash.group(2)), int(m_slash.group(3))
                h = int(m_slash.group(4)) if m_slash.group(4) else 12
                mins = int(m_slash.group(5)) if m_slash.group(5) else 0
                has_time = bool(m_slash.group(4))
                if is_year:
                    new_year = year + adv_num
                    max_d = _py_cal.monthrange(new_year, month)[1]
                    new_day = min(day, max_d)
                    new_month = month
                else:
                    total_m = (month - 1) + adv_num
                    year_delta, m_zero = divmod(total_m, 12)
                    new_year = year + year_delta
                    new_month = m_zero + 1
                    max_d = _py_cal.monthrange(new_year, new_month)[1]
                    new_day = min(day, max_d)
                if has_time:
                    formatted = f"{new_day:02d}/{new_month:02d}/{new_year}, {h:02d}:{mins:02d}"
                else:
                    formatted = f"{new_day:02d}/{new_month:02d}/{new_year}"
                return dt_str[:m_slash.start()] + formatted + dt_str[m_slash.end():]

            # Padrão C: 'Dia X, HH:MM'
            m_dia = re.search(r"Dia\s+(\d+)(?:,\s*(\d{1,2}):(\d{2}))?", dt_str, re.IGNORECASE)
            if m_dia:
                day_num = int(m_dia.group(1))
                h = int(m_dia.group(2)) if m_dia.group(2) else 12
                mins = int(m_dia.group(3)) if m_dia.group(3) else 0
                has_time = bool(m_dia.group(2))
                days_in_year = sum(days_per_month) if days_per_month else 365
                days_in_month = (days_in_year // len(days_per_month)) if days_per_month else 30
                if is_year:
                    new_day = day_num + adv_num * days_in_year
                else:
                    new_day = day_num + adv_num * days_in_month
                if has_time:
                    formatted = f"Dia {new_day}, {h:02d}:{mins:02d}"
                else:
                    formatted = f"Dia {new_day}"
                return dt_str[:m_dia.start()] + formatted + dt_str[m_dia.end():]

        # Para unidades m, h, d, w, converte em minutos
        minutes = parse_time_increment(advance, calendar=calendar)
    else:
        minutes = int(advance)

    if minutes == 0:
        return dt_str

    # Padrão A: 'DD de Mês de YYYY, HH:MM' ou 'DD de Mês de YYYY'
    m_full = re.search(
        r"(\d{1,2})\s+de\s+([A-Za-zçÇãÃõÕéÉêÊíÍóÓúÚ\-]+)\s+de\s+(\d{1,4})(?:,\s*(\d{1,2}):(\d{2}))?",
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
            days = days_per_month
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
            # Fallback conservador para calendários diegéticos ainda não declarados
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


def game_time_to_minutes(dt_str: str, calendar: dict | None = None, fallback_turn: int = 0) -> int:
    """Converte string de tempo diegético em minutos inteiros desde a época (>= 0) para game_time_sort."""
    if not dt_str:
        return max(0, fallback_turn * 60)

    cal = _normalize_calendar(calendar) if calendar else {}
    months = cal.get("months") or []
    days_per_month = cal.get("days_per_month") or []

    m_full = re.search(
        r"(\d{1,2})\s+de\s+([A-Za-zçÇãÃõÕéÉêÊíÍóÓúÚ\-]+)\s+de\s+(\d{1,4})(?:,\s*(\d{1,2}):(\d{2}))?",
        dt_str,
        re.IGNORECASE,
    )
    if m_full:
        day = max(1, int(m_full.group(1)))
        m_name = m_full.group(2)
        year = max(1, int(m_full.group(3)))
        h = int(m_full.group(4)) if m_full.group(4) else 12
        mins = int(m_full.group(5)) if m_full.group(5) else 0
        if months:
            month_idx = next(
                (i for i, name in enumerate(months) if name.casefold() == m_name.casefold()),
                None,
            )
            if month_idx is None:
                raise ValueError(
                    f"Mês '{m_name}' não consta no calendário da campanha. "
                    f"Ajuste 'calendar.months' em regras.md."
                )
            year_days = sum(days_per_month)
            prior_month_days = sum(days_per_month[:month_idx])
            total_days = (year - 1) * year_days + prior_month_days + (day - 1)
            return max(0, total_days * 1440 + h * 60 + mins)
        month_num = MONTHS_MAP.get(m_name.lower(), 1)
        year_days = 360  # fallback conservador de 12 meses de 30 dias, consistente com minutes_to_game_time
        total_days = (year - 1) * year_days + (month_num - 1) * 30 + (day - 1)
        return max(0, total_days * 1440 + h * 60 + mins)

    m_slash = re.search(r"(\d{1,2})/(\d{1,2})/(\d{1,4})(?:,\s*(\d{1,2}):(\d{2}))?", dt_str)
    if m_slash:
        day, month, year = int(m_slash.group(1)), int(m_slash.group(2)), int(m_slash.group(3))
        h = int(m_slash.group(4)) if m_slash.group(4) else 12
        mins = int(m_slash.group(5)) if m_slash.group(5) else 0
        total_days = max(0, year - 1) * 365 + max(0, month - 1) * 30 + max(0, day - 1)
        return max(0, total_days * 1440 + h * 60 + mins)

    m_dia = re.search(r"(?:Dia|Day)\s+(\d+)(?:,\s*(\d{1,2}):(\d{2}))?", dt_str, re.IGNORECASE)
    if m_dia:
        day_num = max(1, int(m_dia.group(1)))
        h = int(m_dia.group(2)) if m_dia.group(2) else 12
        mins = int(m_dia.group(3)) if m_dia.group(3) else 0
        return max(0, (day_num - 1) * 1440 + h * 60 + mins)

    m_time = re.search(r"(\d{1,2}):(\d{2})", dt_str)
    if m_time:
        h, mins = int(m_time.group(1)), int(m_time.group(2))
        return max(0, fallback_turn * 1440 + h * 60 + mins)

    return max(0, fallback_turn * 60)


def validate_game_time(dt_str: str, calendar: dict | None = None) -> None:
    """Valida que a data é interpretável sem ambiguidade de calendário.

    Datas com mês nomeado exigem o mês no calendário declarado ou um mês
    gregoriano conhecido; caso contrário a conversão seria silenciosamente
    errada (mês desconhecido cairia em Janeiro).
    """
    if not isinstance(dt_str, str) or not dt_str.strip():
        raise ValueError("data de jogo vazia ou inválida")
    cal = _normalize_calendar(calendar) if calendar else {}
    months = cal.get("months") or []
    m_full = re.search(
        r"(\d{1,2})\s+de\s+([A-Za-zçÇãÃõÕéÉêÊíÍóÓúÚ\-]+)\s+de\s+(\d{1,4})",
        dt_str,
        re.IGNORECASE,
    )
    if not m_full:
        return
    name = m_full.group(2)
    if months:
        if not any(str(month).casefold() == name.casefold() for month in months):
            raise ValueError(
                f"Mês '{name}' não consta no calendário da campanha. "
                f"Ajuste 'calendar.months' em regras.md."
            )
        return
    if MONTHS_MAP.get(name.lower()) is None:
        raise ValueError(
            f"Mês '{name}' não é gregoriano e a campanha não declara 'calendar.months' em regras.md."
        )


def minutes_to_game_time(
    total_minutes: int,
    template: str,
    calendar: dict | None = None,
) -> str:
    """Converte minutos desde a época em data diegética no formato de ``template``.

    Inversa canônica de :func:`game_time_to_minutes` para os formatos aceitos
    (``Dia N, HH:MM``, ``DD/MM/AAAA, HH:MM`` e ``D de Mês de AAAA, HH:MM``).
    Calendários declarados (``months``/``days_per_month``) governam datas com
    mês nomeado; datas numéricas usam a aritmética convencional de 365/30 já
    usada por :func:`game_time_to_minutes`. Função pura, sem I/O.
    """
    if isinstance(total_minutes, bool) or not isinstance(total_minutes, int):
        raise ValueError("total_minutes deve ser inteiro")
    if total_minutes < 0:
        raise ValueError("total_minutes deve ser >= 0")
    if not isinstance(template, str) or not template.strip():
        raise ValueError("template deve ser texto não vazio")

    cal = _normalize_calendar(calendar) if calendar else {}
    months = cal.get("months") or []
    days_per_month = cal.get("days_per_month") or []

    total_days, rem_minutes = divmod(total_minutes, 1440)
    hour, minute = divmod(rem_minutes, 60)

    m_full = re.search(
        r"(\d{1,2})\s+de\s+([A-Za-zçÇãÃõÕéÉêÊíÍóÓúÚ\-]+)\s+de\s+(\d{1,4})",
        template,
        re.IGNORECASE,
    )
    if m_full:
        if months:
            year_length = sum(days_per_month)
            year = total_days // year_length + 1
            day_of_year = total_days % year_length
            month_idx = 0
            remaining = day_of_year
            while month_idx < len(months) and remaining >= days_per_month[month_idx]:
                remaining -= days_per_month[month_idx]
                month_idx += 1
            if month_idx >= len(months):
                month_idx = len(months) - 1
                remaining = days_per_month[-1] - 1
            day = remaining + 1
            month_name = months[month_idx]
        else:
            year_length = 360
            year = total_days // year_length + 1
            day_of_year = total_days % year_length
            month_num = min(12, day_of_year // 30 + 1)
            day = day_of_year % 30 + 1
            month_name = MONTHS_PT[month_num]
        return f"{day} de {month_name} de {year}, {hour:02d}:{minute:02d}"

    m_slash = re.search(r"(\d{1,2})/(\d{1,2})/(\d{1,4})", template)
    if m_slash:
        year_length, month_length = 365, 30
        year = total_days // year_length + 1
        day_of_year = total_days % year_length
        month = min(12, day_of_year // month_length + 1)
        day = day_of_year % month_length + 1
        return f"{day:02d}/{month:02d}/{year}, {hour:02d}:{minute:02d}"

    if re.search(r"(?:Dia|Day)\s+\d+", template, re.IGNORECASE):
        day = total_days + 1
        return f"Dia {day}, {hour:02d}:{minute:02d}"

    raise ValueError(
        f"Formato de data não reconhecido no template: '{template}'. Use 'Dia N, HH:MM', "
        f"'DD/MM/AAAA, HH:MM' ou 'D de Mês de AAAA, HH:MM'."
    )


def advance_game_time(
    dt_str: str,
    minutes: int,
    calendar: dict | None = None,
) -> str:
    """Avança ``dt_str`` em ``minutes`` minutos preservando a aritmética do calendário.

    Usa :func:`game_time_to_minutes` + :func:`minutes_to_game_time` para garantir
    ida-e-volta consistente (sem ``datetime`` gregoriano em calendários declarados).
    """
    if isinstance(minutes, bool) or not isinstance(minutes, int):
        raise ValueError("minutes deve ser inteiro")
    if minutes < 0:
        raise ValueError("minutes deve ser >= 0")
    base = game_time_to_minutes(dt_str, calendar=calendar)
    return minutes_to_game_time(base + minutes, dt_str, calendar=calendar)


__all__ = [
    "MONTHS_MAP",
    "MONTHS_PT",
    "advance_game_time",
    "advance_time_str",
    "game_time_to_minutes",
    "minutes_to_game_time",
    "parse_time_increment",
    "validate_game_time",
]

