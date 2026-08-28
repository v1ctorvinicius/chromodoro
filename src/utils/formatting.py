from datetime import date, datetime


def format_clock(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    if total < 60:
        return "0 min"
    hours, rem = divmod(total, 3600)
    minutes = rem // 60
    if hours == 0:
        return f"{minutes} min"
    if minutes:
        return f"{hours}h {minutes}m"
    return f"{hours}h"


def format_time(value: datetime) -> str:
    return value.strftime("%H:%M")


def format_day_label(value: datetime, today: date | None = None) -> str:
    reference = today or date.today()
    day = value.date()
    delta = (reference - day).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    return day.strftime("%b %d")


def format_date_heading(value: datetime, today: date | None = None) -> str:
    reference = today or date.today()
    day = value.date()
    if day == reference:
        return "Today"
    if (reference - day).days == 1:
        return "Yesterday"
    return day.strftime("%A, %b %d")
