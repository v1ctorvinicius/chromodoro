from datetime import date, datetime

from utils.formatting import (
    format_clock,
    format_date_heading,
    format_day_label,
    format_duration,
    format_time,
)


def test_format_clock_minutes_and_seconds():
    assert format_clock(0) == "00:00"
    assert format_clock(65) == "01:05"
    assert format_clock(1500) == "25:00"
    assert format_clock(3661) == "1:01:01"


def test_format_duration_buckets():
    assert format_duration(30) == "0 min"
    assert format_duration(300) == "5 min"
    assert format_duration(5100) == "1h 25m"
    assert format_duration(7200) == "2h"


def test_format_time():
    assert format_time(datetime(2026, 8, 20, 14, 5)) == "14:05"


def test_day_labels_relative_to_today():
    today = date(2026, 8, 23)
    assert format_day_label(datetime(2026, 8, 23, 10, 0), today) == "Today"
    assert format_day_label(datetime(2026, 8, 22, 10, 0), today) == "Yesterday"
    assert format_day_label(datetime(2026, 7, 4, 10, 0), today) == "Jul 04"


def test_date_headings():
    today = date(2026, 8, 23)
    assert format_date_heading(datetime(2026, 8, 23, 9, 0), today) == "Today"
    assert format_date_heading(datetime(2026, 8, 21, 9, 0), today) == "Friday, Aug 21"
