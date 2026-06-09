from src.core.version import get_version


def test_get_version_reads_pyproject():
    version = get_version()
    assert version == "3.0.0"
