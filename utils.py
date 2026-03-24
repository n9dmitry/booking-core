from datetime import date, timedelta
from typing import List


def dates_in_range(check_in: date, check_out: date) -> List[date]:
    """
    Возвращает все даты проживания включая заезд И выезд.

    Логика: если гость заезжает 17-го и выезжает 18-го,
    то номер занят и 17-го и 18-го — оба дня нужно проверять.

    17.03 → 17.03  = [17.03]        (заезд и выезд в один день — 1 ночь)
    17.03 → 18.03  = [17.03, 18.03] (1 ночь, но блокируем обе даты)
    17.03 → 19.03  = [17.03, 18.03, 19.03]
    """
    if check_out < check_in:
        return []

    days = []
    d = check_in
    # Включаем check_out (поэтому <=)
    while d <= check_out:
        days.append(d)
        d += timedelta(days=1)
    return days


def nights_count(check_in: date, check_out: date) -> int:
    """Количество ночей — минимум 1."""
    return max(1, (check_out - check_in).days)


def format_date_ru(d: date) -> str:
    months = ["янв", "фев", "мар", "апр", "май", "июн",
              "июл", "авг", "сен", "окт", "ноя", "дек"]
    return f"{d.day} {months[d.month - 1]} {d.year}"


def success_response(data, message: str = "OK") -> dict:
    return {"status": "success", "data": data, "message": message}


def error_response(message: str) -> dict:
    return {"status": "error", "data": None, "message": message}
