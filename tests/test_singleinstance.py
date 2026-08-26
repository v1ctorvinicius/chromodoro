import sys

import pytest

from utils.singleinstance import acquire_instance_lock, mutex_name_for

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="named mutex")


def test_mutex_name_is_deterministic(tmp_path):
    assert mutex_name_for(tmp_path / "a.db") == mutex_name_for(tmp_path / "a.db")
    assert mutex_name_for(tmp_path / "a.db") != mutex_name_for(tmp_path / "b.db")


def test_mutex_name_ignores_case_and_slash_direction(tmp_path):
    lower = tmp_path / "data" / "chromodoro.db"
    upper = tmp_path / "DATA" / "CHROMODORO.DB"
    assert mutex_name_for(lower) == mutex_name_for(upper)


@windows_only
def test_second_acquire_same_db_is_blocked(tmp_path):
    db = tmp_path / "lock.db"
    assert acquire_instance_lock(db) is True
    assert acquire_instance_lock(db) is False


@windows_only
def test_different_dbs_do_not_block_each_other(tmp_path):
    assert acquire_instance_lock(tmp_path / "one.db") is True
    assert acquire_instance_lock(tmp_path / "two.db") is True
