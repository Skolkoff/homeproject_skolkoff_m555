import math

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


def validate_currency_code(code: str) -> str:
    """Validate and normalize a currency code."""
    if not isinstance(code, str) or not code.strip():
        raise CurrencyNotFoundError("Неизвестная валюта ''")
    normalized = code.strip().upper()
    if not normalized.isalpha() or not 2 <= len(normalized) <= 5:
        raise CurrencyNotFoundError(f"Неизвестная валюта '{code}'")
    return normalized


def validate_amount(amount: float) -> float:
    """Return a positive finite amount as a float."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise ValueError("'amount' должен быть положительным числом")
    value = float(amount)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    return value
