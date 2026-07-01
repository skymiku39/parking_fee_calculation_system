import re
from pathlib import Path

import pytest

from src.core import version as version_module
from src.core.version import get_version


def _pyproject_version() -> str:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, "pyproject.toml version not found"
    return match.group(1)


@pytest.fixture(autouse=True)
def clear_version_cache():
    get_version.cache_clear()
    yield
    get_version.cache_clear()


def test_get_version_reads_pyproject():
    assert get_version() == _pyproject_version()


def test_get_version_reads_bundled_file(monkeypatch, tmp_path):
    monkeypatch.setattr(version_module, "is_frozen", lambda: True)
    monkeypatch.setattr(version_module, "bundle_dir", lambda: tmp_path)
    (tmp_path / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    assert get_version() == "9.9.9"


def test_get_version_frozen_fallback_when_no_version_file(monkeypatch):
    monkeypatch.setattr(version_module, "is_frozen", lambda: True)
    monkeypatch.setattr(version_module, "bundle_dir", lambda: Path("/nonexistent"))
    assert get_version() == _pyproject_version()
