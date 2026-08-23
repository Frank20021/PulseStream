import pytest
from sqlalchemy.exc import OperationalError

from shared.retry import backoff_seconds, is_transient


def test_backoff_seconds() -> None:
    assert backoff_seconds(1) == 1
    assert backoff_seconds(2) == 2
    assert backoff_seconds(3) == 4


def test_operational_error_is_transient() -> None:
    error = OperationalError("SELECT 1", {}, Exception("connection refused"))
    assert is_transient(error)


def test_value_error_is_not_transient() -> None:
    assert not is_transient(ValueError("bad payload"))


def test_backoff_rejects_invalid_attempt() -> None:
    with pytest.raises(ValueError):
        backoff_seconds(0)
