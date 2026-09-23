import tomllib
from pathlib import Path

from taskwarrior_textual import __version__


def test_package_version_matches_pyproject() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    payload = tomllib.loads(pyproject.read_text())

    assert payload["project"]["version"] == __version__


def test_console_script_targets_main_entrypoint() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    payload = tomllib.loads(pyproject.read_text())

    assert (
        payload["project"]["scripts"]["taskwarrior-textual"]
        == "taskwarrior_textual.__main__:main"
    )
