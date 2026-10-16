from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError
from valutatrade_hub.core.utils import validate_currency_code


class Currency(ABC):
    """Base model for a supported currency."""

    kind = "CURRENCY"

    def __init__(self, name: str, code: str) -> None:
        normalized = validate_currency_code(code)
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты не может быть пустым")
        self.name = name.strip()
        self.code = normalized

    @abstractmethod
    def get_display_info(self) -> str:
        """Return a short display label."""


class FiatCurrency(Currency):
    """Fiat currency with an issuing country or region."""

    kind = "FIAT"

    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name, code)
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Cryptocurrency with algorithm and market capitalization."""

    kind = "CRYPTO"

    def __init__(
        self,
        name: str,
        code: str,
        algorithm: str,
        market_cap: float = 0.0,
    ) -> None:
        super().__init__(name, code)
        self.algorithm = algorithm
        self.market_cap = float(market_cap)

    def get_display_info(self) -> str:
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"
        )


_CURRENCIES = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "GBP": FiatCurrency("British Pound", "GBP", "United Kingdom"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.45e11),
    "SOL": CryptoCurrency("Solana", "SOL", "Proof of Stake", 8.0e10),
}


def get_currency(code: str) -> Currency:
    """Return currency metadata for a supported code."""
    normalized = validate_currency_code(code)
    try:
        return _CURRENCIES[normalized]
    except KeyError as error:
        raise CurrencyNotFoundError(f"Неизвестная валюта '{normalized}'") from error


def get_supported_currencies() -> dict[str, Currency]:
    """Return a copy of the supported currency registry."""
    return _CURRENCIES.copy()
