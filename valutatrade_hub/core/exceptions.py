class ValutaTradeError(Exception):
    """Base exception for errors shown to a CLI user."""


class UserNotFoundError(ValutaTradeError):
    """Raised when a username does not exist."""


class UsernameAlreadyExistsError(ValutaTradeError):
    """Raised when a username is already registered."""


class InvalidPasswordError(ValutaTradeError):
    """Raised when a password is invalid or too short."""


class InsufficientFundsError(ValutaTradeError):
    """Raised when a wallet cannot cover a withdrawal."""


class WalletNotFoundError(ValutaTradeError):
    """Raised when a portfolio has no wallet for a currency."""


class CurrencyNotFoundError(ValutaTradeError):
    """Raised when a currency code is not supported."""


class ApiRequestError(ValutaTradeError):
    """Raised when an exchange-rate API request fails."""

    def __init__(self, reason: str) -> None:
        """Create an API error with a user-readable reason."""
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")


class NotLoggedInError(ValutaTradeError):
    """Raised when an authenticated command is used before login."""
