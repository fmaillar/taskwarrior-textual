import runpy
import sys

import pytest

import taskwarrior_textual.__main__ as main_module
import taskwarrior_textual.app
from taskwarrior_textual.config import ConfigError


def test_main_delegates_to_app_run(monkeypatch) -> None:
    called = []
    monkeypatch.setattr(main_module, "run", lambda: called.append(True))
    main_module.main([])
    assert called == [True]


def test_main_reports_configuration_error(monkeypatch, capsys) -> None:
    def fail() -> None:
        raise ConfigError("bad planning config")

    monkeypatch.setattr(main_module, "run", fail)

    with pytest.raises(SystemExit) as exc:
        main_module.main([])

    assert exc.value.code == 2
    assert "configuration error: bad planning config" in capsys.readouterr().err


def test_main_version_does_not_launch_app(monkeypatch, capsys) -> None:
    called = []
    monkeypatch.setattr(main_module, "run", lambda: called.append(True))

    main_module.main(["--version"])

    assert called == []
    assert capsys.readouterr().out.strip() == "taskwarrior-textual 0.1.0"


def test_main_prints_config_path_without_loading_config(monkeypatch, capsys, tmp_path) -> None:
    path = tmp_path / "config.toml"
    monkeypatch.setattr(main_module, "default_config_path", lambda: path)
    monkeypatch.setattr(
        main_module,
        "load_planning_settings",
        lambda: (_ for _ in ()).throw(AssertionError("should not load")),
    )

    main_module.main(["--config-path"])

    assert capsys.readouterr().out.strip() == str(path)


def test_main_check_config_validates_without_launching_app(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    path = tmp_path / "config.toml"
    called = []
    monkeypatch.setattr(main_module, "default_config_path", lambda: path)
    monkeypatch.setattr(main_module, "load_planning_settings", lambda: object())
    monkeypatch.setattr(main_module, "run", lambda: called.append(True))

    main_module.main(["--check-config"])

    assert called == []
    assert capsys.readouterr().out.strip() == f"configuration ok: {path}"


def test_main_check_config_reports_invalid_configuration(monkeypatch, capsys) -> None:
    def fail():
        raise ConfigError("bad planning config")

    monkeypatch.setattr(main_module, "load_planning_settings", fail)

    with pytest.raises(SystemExit) as exc:
        main_module.main(["--check-config"])

    assert exc.value.code == 2
    assert "configuration error: bad planning config" in capsys.readouterr().err


def test_module_execution_calls_run(monkeypatch) -> None:
    called = []
    monkeypatch.setattr(taskwarrior_textual.app, "run", lambda: called.append(True))
    monkeypatch.setattr(sys, "argv", ["taskwarrior-textual"])
    monkeypatch.delitem(sys.modules, "taskwarrior_textual.__main__", raising=False)
    runpy.run_module("taskwarrior_textual.__main__", run_name="__main__")
    assert called == [True]
