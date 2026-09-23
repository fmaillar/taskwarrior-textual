import runpy

import taskwarrior_textual.app
import taskwarrior_textual.__main__ as main_module


def test_main_delegates_to_app_run(monkeypatch) -> None:
    called = []
    monkeypatch.setattr(main_module, "run", lambda: called.append(True))
    main_module.main()
    assert called == [True]


def test_module_execution_calls_run(monkeypatch) -> None:
    called = []
    monkeypatch.setattr(taskwarrior_textual.app, "run", lambda: called.append(True))
    runpy.run_module("taskwarrior_textual.__main__", run_name="__main__")
    assert called == [True]
