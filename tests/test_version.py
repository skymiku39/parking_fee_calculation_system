import re
from pathlib import Path

from src.core.version import get_version


def _pyproject_version() -> str:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, "pyproject.toml version not found"
    return match.group(1)


def test_get_version_reads_pyproject():
    assert get_version() == _pyproject_version()
