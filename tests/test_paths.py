import json
import os

import pytest

from src.core.paths import (
    DATA_ENV_VAR,
    DATA_FILES,
    ensure_data_dir,
    resolve_data_dir,
)


def test_resolve_data_dir_uses_config_in_dev(monkeypatch):
    monkeypatch.delenv(DATA_ENV_VAR, raising=False)
    data_dir = resolve_data_dir()
    assert data_dir.name == "config"
    assert data_dir.is_dir()


def test_resolve_data_dir_env_override(tmp_path, monkeypatch):
    custom = tmp_path / "custom_data"
    custom.mkdir()
    monkeypatch.setenv(DATA_ENV_VAR, str(custom))
    assert resolve_data_dir() == custom.resolve()


def test_ensure_data_dir_seeds_missing_files(tmp_path, monkeypatch):
    seed = tmp_path / "seed"
    seed.mkdir()
    for name in DATA_FILES:
        (seed / name).write_text(json.dumps({"seed": name}), encoding="utf-8")

    target = tmp_path / "runtime"
    monkeypatch.setenv(DATA_ENV_VAR, str(target))

    from src.core import paths

    monkeypatch.setattr(paths, "default_seed_dir", lambda: seed)

    result = ensure_data_dir(seed_if_missing=True)
    assert result == target.resolve()
    for name in DATA_FILES:
        assert (target / name).is_file()
