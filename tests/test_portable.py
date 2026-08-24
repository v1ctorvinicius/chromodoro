from pathlib import Path

import storage.database as database_module
from storage.database import default_db_path, portable_data_dir


def test_env_override_wins_over_portable_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(database_module, "candidate_roots", lambda: [tmp_path])
    monkeypatch.setenv("CHROMODORO_DB", str(tmp_path / "custom.db"))

    assert default_db_path() == Path(tmp_path / "custom.db")


def test_portable_data_dir_is_used_when_present(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(database_module, "candidate_roots", lambda: [tmp_path])
    monkeypatch.delenv("CHROMODORO_DB", raising=False)

    assert portable_data_dir() == data_dir
    assert default_db_path() == data_dir / "chromodoro.db"


def test_falls_back_to_appdata_without_portable_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "candidate_roots", lambda: [tmp_path])
    monkeypatch.delenv("CHROMODORO_DB", raising=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("APPDATA", str(fake_home))

    path = default_db_path()

    assert path == fake_home / "Chromodoro" / "chromodoro.db"
    assert path.parent.is_dir()


def test_first_matching_candidate_root_wins(tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    for folder in (first, second):
        (folder / "data").mkdir(parents=True)
    monkeypatch.setattr(database_module, "candidate_roots", lambda: [first, second])
    monkeypatch.delenv("CHROMODORO_DB", raising=False)

    assert portable_data_dir() == first / "data"
