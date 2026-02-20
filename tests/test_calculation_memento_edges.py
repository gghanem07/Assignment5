from decimal import Decimal

from app.calculation import Calculation
from app.calculator_memento import CalculatorMemento
from app.exceptions import OperationError


def test_calculation_str_and_repr_and_eq_other_type():
    calc = Calculation(operation="Addition", operand1=Decimal("1"), operand2=Decimal("2"))
    calc.result = Decimal("3")

    s = str(calc)
    r = repr(calc)

    assert "Addition" in s
    assert "Calculation(" in r
    assert (calc == "not a calc") is False


def test_calculation_error_wrapper_branch():
    """
    Covers Calculation error-wrapper branch even if the failure happens during
    construction OR during perform().
    """
    try:
        calc = Calculation(operation="Power", operand1=Decimal("1e308"), operand2=Decimal("2"))
        calc.perform()
        assert False, "Expected an OperationError but calculation succeeded"
    except Exception as e:
        assert isinstance(e, OperationError)
        assert "Calculation failed:" in str(e)


def test_memento_to_dict_and_from_dict():
    calc = Calculation(operation="Addition", operand1=Decimal("1"), operand2=Decimal("2"))
    calc.result = Decimal("3")

    m1 = CalculatorMemento(history=[calc])
    data = m1.to_dict()

    m2 = CalculatorMemento.from_dict(data)
    assert len(m2.history) == 1