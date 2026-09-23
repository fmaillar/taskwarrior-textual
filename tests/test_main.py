import runpy
import sys

import pytest

import taskwarrior_textual.__main__ as main_module
import taskwarrior_textual.app
from taskwarrior_textual.config import ConfigError


def test_main_delegates_to_app_run(monkeypatch) -> None:
    called = []
    monkeypatch.setattr(main_module, "run", lambda: called.append(True))
    main_module.main()
    assert called == [True]


def test_main_reports_configuration_error(monkeypatch, capsys) -> None:
    def fail() -> None:
        raise ConfigError("bad planning config")

    monkeypatch.setattr(main_module, "run", fail)

    with pytest.raises(SystemExit) as exc:
        main_module.main()

    assert exc.value.code == 2
    assert "configuration error: bad planning config" in capsys.readouterr().err


def test_module_execution_calls_run(monkeypatch) -> None:
    called = []
    monkeypatch.setattr(taskwarrior_textual.app, "run", lambda: called.append(True))
    monkeypatch.delitem(sys.modules, "taskwarrior_textual.__main__", raising=False)
    runpy.run_module("taskwarrior_textual.__main__", run_name="__main__")
    assert called == [True]
