import json
import sys

from src.core import paths
from src.core.paths import (
    DATA_ENV_VAR,
    DATA_FILES,
    bundle_dir,
    default_seed_dir,
    ensure_data_dir,
    executable_dir,
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


def test_ensure_data_dir_without_seed_skips_copy(tmp_path, monkeypatch):
    target = tmp_path / "runtime"
    monkeypatch.setenv(DATA_ENV_VAR, str(target))

    result = ensure_data_dir(seed_if_missing=False)
    assert result == target.resolve()
    assert result.is_dir()
    for name in DATA_FILES:
        assert not (target / name).exists()


def test_frozen_paths_use_executable_and_bundle(tmp_path, monkeypatch):
    monkeypatch.delenv(DATA_ENV_VAR, raising=False)
    exe = tmp_path / "app" / "ParkingCalculator.exe"
    exe.parent.mkdir(parents=True)
    meipass = tmp_path / "bundle"
    meipass.mkdir()

    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "executable", str(exe), raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)

    assert executable_dir() == exe.parent.resolve()
    assert bundle_dir() == meipass
    assert resolve_data_dir() == exe.parent.resolve() / "data"


def test_frozen_default_seed_dir_prefers_defaults(tmp_path, monkeypatch):
    meipass = tmp_path / "bundle"
    (meipass / "defaults").mkdir(parents=True)

    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)

    assert default_seed_dir() == meipass / "defaults"
