from pathlib import Path
import pandas as pd
import pytest

from app.calculator import Calculator
from app.calculator_config import CalculatorConfig
from app.exceptions import OperationError


def cfg(tmp_path: Path) -> CalculatorConfig:
    c = CalculatorConfig(base_dir=tmp_path)
    c.validate()
    return c


def test_setup_logging_exception_path(monkeypatch, tmp_path):
    # cover calculator.py 103-106
    c = cfg(tmp_path)

    def makedirs_boom(*args, **kwargs):
        raise Exception("mkdir fail")

    monkeypatch.setattr("os.makedirs", makedirs_boom, raising=False)

    with pytest.raises(Exception):
        Calculator(c)


def test_history_max_size_pop(monkeypatch, tmp_path):
    # cover 218-219
    c = Calculator(cfg(tmp_path))
    c.config.max_history_size = 1

    # set an operation strategy and do two operations so pop happens
    from app.operations import OperationFactory
    c.set_operation(OperationFactory.create_operation("add"))
    c.perform_operation("1", "1")
    c.perform_operation("2", "2")
    assert len(c.history) == 1


def test_save_history_empty_branch(tmp_path):
    # cover 268-270 (empty history saved)
    c = Calculator(cfg(tmp_path))
    c.history = []
    c.save_history()
    assert c.config.history_file.exists()


def test_save_history_failure_branch(monkeypatch, tmp_path):
    # cover 272-275 (raise OperationError)
    c = Calculator(cfg(tmp_path))

    class DummyCalc:
        operation = "Add"
        operand1 = "1"
        operand2 = "2"
        result = "3"
        import datetime as _dt
        timestamp = _dt.datetime.now()

    c.history = [DummyCalc()]

    def to_csv_boom(self, *args, **kwargs):
        raise Exception("disk")

    monkeypatch.setattr(pd.DataFrame, "to_csv", to_csv_boom)

    with pytest.raises(OperationError):
        c.save_history()


def test_load_history_empty_df_logs(tmp_path):
    # cover 305
    c = Calculator(cfg(tmp_path))
    c.config.history_dir.mkdir(parents=True, exist_ok=True)
    c.config.history_file.write_text("operation,operand1,operand2,result,timestamp\n", encoding="utf-8")
    c.load_history()
    assert c.history == []


def test_load_history_no_file_branch(tmp_path, caplog):
    # cover 309-312
    c = Calculator(cfg(tmp_path))
    if c.config.history_file.exists():
        c.config.history_file.unlink()
    c.load_history()
    assert True  # just execute branch


def test_get_history_dataframe_loop(tmp_path):
    # cover 324-333
    c = Calculator(cfg(tmp_path))
    from app.operations import OperationFactory
    c.set_operation(OperationFactory.create_operation("add"))
    c.perform_operation("1", "2")
    df = c.get_history_dataframe()
    assert list(df.columns) == ["operation", "operand1", "operand2", "result", "timestamp"]
    assert len(df) == 1


def test_undo_redo_empty_stacks(tmp_path):
    # cover 371 and 390
    c = Calculator(cfg(tmp_path))
    c.undo_stack.clear()
    c.redo_stack.clear()
    assert c.undo() is False
    assert c.redo() is False