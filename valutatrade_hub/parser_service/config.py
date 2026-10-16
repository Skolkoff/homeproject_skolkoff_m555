import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParserConfig:
    """Configuration for supported currency providers."""

    exchange_rate_api_key: str | None = field(
        default_factory=lambda: os.getenv("EXCHANGERATE_API_KEY") or None
    )
    coingecko_url: str = "https://api.coingecko.com/api/v3/simple/price"
    exchange_rate_api_url: str = "https://v6.exchangerate-api.com/v6"
    base_fiat_currency: str = "USD"
    fiat_currencies: tuple[str, ...] = ("EUR", "GBP", "RUB")
    crypto_id_map: dict[str, str] = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )
    request_timeout: int = 10
