import inspect
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from typing import Any, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])
_LOGGER = logging.getLogger("valutatrade.actions")


def log_action(action: str, verbose: bool = False) -> Callable[[F], F]:
    """Log an operation and re-raise any exception it produces."""

    def decorate(function: F) -> F:
        signature = inspect.signature(function)

        @wraps(function)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            bound = signature.bind_partial(*args, **kwargs)
            values = bound.arguments
            user = values.get("user")
            username = getattr(user, "username", values.get("username", "unknown"))
            currency_code = values.get("currency_code", "-")
            amount = values.get("amount", "-")
            timestamp = datetime.now(UTC).isoformat()
            fields = (
                f"timestamp={timestamp} action={action} username={username!r} "
                f"currency={currency_code!r} amount={amount}"
            )
            try:
                result = function(*args, **kwargs)
                if isinstance(result, dict):
                    rate = result.get("rate")
                    base = result.get("base")
                    if rate is not None:
                        fields += f" rate={rate} base={base!r}"
                    if verbose and "previous_balance" in result:
                        fields += (
                            f" balance={result['previous_balance']}"
                            f"->{result['new_balance']}"
                        )
                _LOGGER.info("%s result=OK", fields)
                return result
            except Exception as error:
                _LOGGER.info(
                    "%s result=ERROR error_type=%s error_message=%r",
                    fields,
                    type(error).__name__,
                    str(error),
                )
                raise

        return cast(F, wrapped)

    return decorate
