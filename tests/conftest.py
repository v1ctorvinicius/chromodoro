from datetime import datetime, timedelta

import pytest

from storage.database import Database


class FakeClock:
    def __init__(self, start: datetime | None = None):
        self._now = start or datetime(2026, 8, 20, 9, 0, 0)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now = self._now + timedelta(seconds=seconds)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    yield database
    database.close()
