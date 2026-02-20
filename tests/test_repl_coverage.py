import builtins
from decimal import Decimal
import pytest

import app.calculator_repl as repl
from app.exceptions import ValidationError, OperationError


class FakeCalculator:
    """Deterministic fake to drive REPL branches without touching real FS/pandas."""

    def __init__(self):
        self._history_calls = 0
        self._undo_calls = 0
        self._redo_calls = 0

    def add_observer(self, obs):
        return None

    def save_history(self):
        # will be monkeypatched per-test when needed
        return None

    def load_history(self):
        return None

    def show_history(self):
        # first call empty, second call non-empty => covers both branches
        self._history_calls += 1
        if self._history_calls == 1:
            return []
        return ["Add(1,2) = 3", "Multiply(2,3) = 6"]

    def clear_history(self):
        return None

    def undo(self):
        self._undo_calls += 1
        return self._undo_calls == 1  # True then False

    def redo(self):
        self._redo_calls += 1
        return self._redo_calls == 1  # True then False

    def set_operation(self, op):
        self._op = op

    def perform_operation(self, a, b):
        if a == "bad":
            raise ValidationError("Invalid number")
        if a == "operr":
            raise OperationError("Operation failed")
        if a == "boom":
            raise RuntimeError("Unexpected")
        return Decimal("2.0")  # Decimal normalize branch


class DummyFactory:
    @staticmethod
    def create_operation(cmd):
        return object()


def feed(monkeypatch, inputs):
    it = iter(inputs)

    def fake_input(prompt=""):
        v = next(it)
        # allow sentinel exceptions to simulate Ctrl+C / Ctrl+D
        if v == "__KEYBOARDINTERRUPT__":
            raise KeyboardInterrupt()
        if v == "__EOFERROR__":
            raise EOFError()
        if v == "__GENERICEXC__":
            raise Exception("generic")
        return v

    monkeypatch.setattr(builtins, "input", fake_input)


def test_repl_main_paths(monkeypatch, capsys):
    # patch dependencies
    fake_calc = FakeCalculator()
    monkeypatch.setattr(repl, "Calculator", lambda: fake_calc)
    monkeypatch.setattr(repl, "LoggingObserver", lambda: object())
    monkeypatch.setattr(repl, "AutoSaveObserver", lambda c: object())
    monkeypatch.setattr(repl, "OperationFactory", DummyFactory)

    inputs = [
        "help",
        "history",          # empty
        "history",          # non-empty with enumerate
        "clear",
        "undo", "undo",     # True then False
        "redo", "redo",     # True then False
        "save",
        "load",
        "add", "cancel",                # cancel at first number
        "add", "1", "cancel",           # cancel at second number
        "add", "bad", "2",              # ValidationError
        "add", "operr", "2",            # OperationError
        "add", "boom", "2",             # unexpected Exception branch
        "add", "2", "2",                # success + Decimal.normalize
        "wat",                          # unknown command
        "exit",
    ]
    feed(monkeypatch, inputs)

    repl.calculator_repl()
    out = capsys.readouterr().out.lower()

    assert "available commands" in out
    assert "no calculations in history" in out
    assert "calculation history" in out
    assert "history cleared" in out
    assert "operation undone" in out
    assert "nothing to undo" in out
    assert "operation redone" in out
    assert "nothing to redo" in out
    assert "history saved successfully" in out
    assert "history loaded successfully" in out
    assert "operation cancelled" in out
    assert "error:" in out
    assert "unexpected error" in out
    assert "result:" in out
    assert "unknown command" in out
    assert "goodbye" in out


def test_repl_exit_save_history_failure(monkeypatch, capsys):
    fake_calc = FakeCalculator()

    def boom():
        raise Exception("fs fail")
    fake_calc.save_history = boom

    monkeypatch.setattr(repl, "Calculator", lambda: fake_calc)
    monkeypatch.setattr(repl, "LoggingObserver", lambda: object())
    monkeypatch.setattr(repl, "AutoSaveObserver", lambda c: object())

    feed(monkeypatch, ["exit"])
    repl.calculator_repl()

    out = capsys.readouterr().out.lower()
    assert "warning: could not save history" in out
    assert "goodbye" in out


def test_repl_save_and_load_failures(monkeypatch, capsys):
    fake_calc = FakeCalculator()

    def boom_save():
        raise Exception("save fail")
    def boom_load():
        raise Exception("load fail")

    fake_calc.save_history = boom_save
    fake_calc.load_history = boom_load

    monkeypatch.setattr(repl, "Calculator", lambda: fake_calc)
    monkeypatch.setattr(repl, "LoggingObserver", lambda: object())
    monkeypatch.setattr(repl, "AutoSaveObserver", lambda c: object())

    feed(monkeypatch, ["save", "load", "exit"])
    repl.calculator_repl()

    out = capsys.readouterr().out.lower()
    assert "error saving history" in out
    assert "error loading history" in out


def test_repl_keyboard_interrupt_path(monkeypatch, capsys):
    fake_calc = FakeCalculator()
    monkeypatch.setattr(repl, "Calculator", lambda: fake_calc)
    monkeypatch.setattr(repl, "LoggingObserver", lambda: object())
    monkeypatch.setattr(repl, "AutoSaveObserver", lambda c: object())

    feed(monkeypatch, ["__KEYBOARDINTERRUPT__", "exit"])
    repl.calculator_repl()
    out = capsys.readouterr().out.lower()
    assert "operation cancelled" in out


def test_repl_eof_path(monkeypatch, capsys):
    fake_calc = FakeCalculator()
    monkeypatch.setattr(repl, "Calculator", lambda: fake_calc)
    monkeypatch.setattr(repl, "LoggingObserver", lambda: object())
    monkeypatch.setattr(repl, "AutoSaveObserver", lambda c: object())

    feed(monkeypatch, ["__EOFERROR__"])
    repl.calculator_repl()
    out = capsys.readouterr().out.lower()
    assert "input terminated" in out


def test_repl_generic_exception_in_loop(monkeypatch, capsys):
    fake_calc = FakeCalculator()
    monkeypatch.setattr(repl, "Calculator", lambda: fake_calc)
    monkeypatch.setattr(repl, "LoggingObserver", lambda: object())
    monkeypatch.setattr(repl, "AutoSaveObserver", lambda c: object())

    feed(monkeypatch, ["__GENERICEXC__", "exit"])
    repl.calculator_repl()
    out = capsys.readouterr().out.lower()
    assert "error:" in out


def test_repl_fatal_init_exception(monkeypatch):
    # Force Calculator() to fail => hits lines 159-163
    monkeypatch.setattr(repl, "Calculator", lambda: (_ for _ in ()).throw(Exception("init fail")))

    with pytest.raises(Exception):
        feed(monkeypatch, ["exit"])
        repl.calculator_repl()