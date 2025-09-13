import pytest

from ..utils.expression import eval_expression


@pytest.mark.parametrize(
    "expr,row,header_map,expected",
    [
        (
            "U1_MW+U2_MW",
            ["599.95", "405.54", "50.04", "4.93", "49.89"],
            {"u1_mw": 2, "u2_mw": 4},
            99.93,
        ),
        ("U1_MW-U2_MW", ["", "", "60.0", "", "15.5"], {"u1_mw": 2, "u2_mw": 4}, 44.5),
        ("U1_MW*U2_MW", ["", "", "5.0", "", "2.0"], {"u1_mw": 2, "u2_mw": 4}, 10.0),
        ("MISSING+U1_MW", ["", "", "50.0"], {"u1_mw": 2}, None),
    ],
)
def test_eval_expression(expr, row, header_map, expected):
    result = eval_expression(expr, row, header_map)
    if expected is None:
        assert result is None
    else:
        assert round(result, 2) == pytest.approx(expected, abs=1e-2)


def test_eval_expression_invalid_token():
    row = ["", "", "5.0", "", "2.0"]
    header_map = {"u1_mw": 2, "u2_mw": 4}
    assert eval_expression("U1_MW+@U2_MW", row, header_map) is None


def test_eval_expression_division_by_zero():
    row = ["", "", "5.0", "", "0"]
    header_map = {"u1_mw": 2, "u2_mw": 4}
    assert eval_expression("U1_MW/U2_MW", row, header_map) is None


def test_eval_expression_missing_header_map():
    row = ["", "", "5.0", "", "2.0"]
    header_map = {}  # empty
    assert eval_expression("U1_MW+U2_MW", row, header_map) is None


def test_eval_expression_non_numeric():
    row = ["", "", "fifty", "", "two"]
    header_map = {"u1_mw": 2, "u2_mw": 4}
    assert eval_expression("U1_MW+U2_MW", row, header_map) is None
