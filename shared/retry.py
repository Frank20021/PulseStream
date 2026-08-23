from sqlalchemy.exc import InterfaceError, OperationalError

MAX_PROCESSING_ATTEMPTS = 4


class TransientProcessingError(Exception):
    """A temporary failure that should be retried."""


def backoff_seconds(attempt: int) -> int:
    """Seconds to wait after a failed attempt before the next try.

    Attempt 1 → 1s, attempt 2 → 2s, attempt 3 → 4s.
    After attempt 4 the caller sends the event to the dead-letter topic.
    """
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    return 2 ** (attempt - 1)


def is_transient(error: BaseException) -> bool:
    return isinstance(error, (OperationalError, InterfaceError, TimeoutError, ConnectionError, OSError))
