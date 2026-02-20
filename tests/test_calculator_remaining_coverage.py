from pathlib import Path
import pandas as pd
import pytest

from app.calculator import Calculator
from app.calculator_config import CalculatorConfig
from app.exceptions import OperationError
from app.operations import OperationFactory


def cfg(tmp_path: Path) -> CalculatorConfig:
    c = CalculatorConfig(base_dir=tmp_path)
    c.validate()
    return c


def test_init_load_history_exception_path(monkeypatch, tmp_path):
    called = {"warning": False}

    def fake_warning(msg):
        if "Could not load existing history" in msg:
            called["warning"] = True

    def boom(self):
        raise Exception("load fails")

    monkeypatch.setattr(Calculator, "load_history", boom)
    monkeypatch.setattr("app.calculator.logging.warning", fake_warning)

    c = Calculator(cfg(tmp_path))
    assert c is not None
    assert called["warning"] is True


def test_setup_logging_exception_path(monkeypatch, tmp_path, capsys):
    c = Calculator(cfg(tmp_path))

    def boom(*args, **kwargs):
        raise Exception("mkdir fail")

    monkeypatch.setattr("os.makedirs", boom, raising=False)

    with pytest.raises(Exception):
        c._setup_logging()

    out = capsys.readouterr().out.lower()
    assert "error setting up logging" in out


def test_perform_operation_generic_exception_wrapped(monkeypatch, tmp_path):
    c = Calculator(cfg(tmp_path))
    c.set_operation(OperationFactory.create_operation("add"))

    def boom_validate_number(value, config):
        raise RuntimeError("validator blew up")

    monkeypatch.setattr("app.calculator.InputValidator.validate_number", boom_validate_number)

    with pytest.raises(OperationError) as e:
        c.perform_operation("1", "2")

    assert "operation failed" in str(e.value).lower()


def test_load_history_exception_path_hits_309_312(monkeypatch, tmp_path):
    """
    Covers calculator.py lines 309-312:
    Force an exception inside load_history() and ensure it raises OperationError.
    """
    c = Calculator(cfg(tmp_path))

    # Make exists() True so we enter the branch that reads CSV,
    # then force pd.read_csv to throw.
    c.config.history_dir.mkdir(parents=True, exist_ok=True)
    c.config.history_file.write_text("operation,operand1,operand2,result,timestamp\n", encoding="utf-8")

    def boom_read_csv(*args, **kwargs):
        raise Exception("corrupt csv")

    monkeypatch.setattr(pd, "read_csv", boom_read_csv)

    with pytest.raises(OperationError) as e:
        c.load_history()

    assert "failed to load history" in str(e.value).lower()


def test_show_history_formats_entries(tmp_path):
    c = Calculator(cfg(tmp_path))
    c.set_operation(OperationFactory.create_operation("add"))
    c.perform_operation("1", "2")

    hist = c.show_history()
    assert isinstance(hist, list)
    assert len(hist) == 1
    assert "=" in hist[0]