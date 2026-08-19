"""Tests for shared Jinja2 template helpers."""

from review_app.models import CheckResult
from review_app.templating import lang_name, sort_checks


def _check(check_id: str, value: object, threshold: object | None) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        label=check_id,
        value=value,
        threshold=threshold,
        status="pass",
    )


def test_sort_checks_orders_threshold_first_then_none_then_unknown() -> None:
    checks = [
        _check("no_threshold", 5, None),
        _check("unknown_no_threshold", "unknown", None),
        _check("with_threshold", 5, [0, 10]),
        _check("unknown_with_threshold", "unknown", [0, 10]),
    ]
    result = [c.check_id for c in sort_checks(checks)]
    assert result == [
        "with_threshold",
        "no_threshold",
        "unknown_no_threshold",
        "unknown_with_threshold",
    ]


def test_sort_checks_preserves_registry_order_within_groups() -> None:
    checks = [
        _check("a_no_threshold", 1, None),
        _check("b_no_threshold", 2, None),
    ]
    result = [c.check_id for c in sort_checks(checks)]
    assert result == ["a_no_threshold", "b_no_threshold"]


def test_sort_checks_returns_new_list() -> None:
    checks = [_check("with_threshold", 5, [0, 10])]
    result = sort_checks(checks)
    assert result == checks
    assert result is not checks


def test_lang_name() -> None:
    assert lang_name("DE") == "German"
    assert lang_name("ZD") == "Zurich (Swiss) German"
    assert lang_name("XX") == "XX"
