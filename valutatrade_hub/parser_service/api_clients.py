import math
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    """Common interface for external rate providers."""

    source = "API"

    @abstractmethod
    def fetch_rates(self) -> dict[str, dict[str, Any]]:
        """Fetch and normalize exchange rates."""


class CoinGeckoClient(BaseApiClient):
    """Fetch crypto-to-USD rates from CoinGecko."""

    source = "CoinGecko"

    def __init__(self, config: ParserConfig | None = None) -> None:
        """Create the client with the supplied or default configuration."""
        self.config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, dict[str, Any]]:
        """Fetch supported cryptocurrency rates from CoinGecko."""
        ids = ",".join(self.config.crypto_id_map.values())
        started = perf_counter()
        try:
            response = requests.get(
                self.config.coingecko_url,
                params={"ids": ids, "vs_currencies": "usd"},
                timeout=self.config.request_timeout,
            )
            if response.status_code != 200:
                raise ApiRequestError(f"CoinGecko вернул HTTP {response.status_code}")
            payload = response.json()
        except requests.exceptions.RequestException as error:
            raise ApiRequestError("CoinGecko временно недоступен") from error
        except ValueError as error:
            if isinstance(error, ApiRequestError):
                raise
            raise ApiRequestError("CoinGecko вернул некорректный JSON") from error

        if not isinstance(payload, dict):
            raise ApiRequestError("CoinGecko вернул данные неверного формата")
        updated_at = datetime.now(UTC).isoformat()
        request_ms = round((perf_counter() - started) * 1000)
        result: dict[str, dict[str, Any]] = {}
        for code, raw_id in self.config.crypto_id_map.items():
            coin = payload.get(raw_id, {})
            value = coin.get("usd") if isinstance(coin, dict) else None
            if (
                isinstance(value, (int, float))
                and math.isfinite(float(value))
                and value > 0
            ):
                result[f"{code}_USD"] = {
                    "rate": float(value),
                    "updated_at": updated_at,
                    "source": self.source,
                    "meta": {
                        "raw_id": raw_id,
                        "request_ms": request_ms,
                        "status_code": response.status_code,
                        "etag": response.headers.get("ETag"),
                    },
                }
        if not result:
            raise ApiRequestError("CoinGecko не вернул курсы поддерживаемых валют")
        return result


class ExchangeRateApiClient(BaseApiClient):
    """Fetch fiat-to-USD rates from ExchangeRate-API."""

    source = "ExchangeRate-API"

    def __init__(self, config: ParserConfig | None = None) -> None:
        """Create the client with the supplied or default configuration."""
        self.config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, dict[str, Any]]:
        """Fetch supported fiat rates from ExchangeRate-API."""
        key = self.config.exchange_rate_api_key
        if not key:
            raise ApiRequestError(
                "не задан EXCHANGERATE_API_KEY; добавьте ключ в локальный .env"
            )
        url = (
            f"{self.config.exchange_rate_api_url.rstrip('/')}/"
            f"{key}/latest/{self.config.base_fiat_currency}"
        )
        try:
            response = requests.get(url, timeout=self.config.request_timeout)
            if response.status_code != 200:
                raise ApiRequestError(
                    f"ExchangeRate-API вернул HTTP {response.status_code}"
                )
            payload = response.json()
        except requests.exceptions.RequestException as error:
            raise ApiRequestError("ExchangeRate-API временно недоступен") from error
        except ValueError as error:
            if isinstance(error, ApiRequestError):
                raise
            raise ApiRequestError(
                "ExchangeRate-API вернул некорректный JSON"
            ) from error

        if not isinstance(payload, dict) or payload.get("result") != "success":
            reason = (
                payload.get("error-type", "неизвестная ошибка")
                if isinstance(payload, dict)
                else "данные неверного формата"
            )
            raise ApiRequestError(f"ExchangeRate-API: {reason}")
        rates = payload.get("conversion_rates", payload.get("rates", {}))
        if not isinstance(rates, dict):
            raise ApiRequestError("ExchangeRate-API вернул некорректный список курсов")

        updated_at = self._updated_at(payload)
        result = {}
        for code in self.config.fiat_currencies:
            usd_to_fiat = rates.get(code)
            if (
                isinstance(usd_to_fiat, (int, float))
                and math.isfinite(float(usd_to_fiat))
                and usd_to_fiat > 0
            ):
                result[f"{code}_USD"] = {
                    "rate": 1.0 / float(usd_to_fiat),
                    "updated_at": updated_at,
                    "source": self.source,
                    "meta": {"status_code": response.status_code},
                }
        if not result:
            raise ApiRequestError("ExchangeRate-API не вернул нужные фиатные курсы")
        return result

    @staticmethod
    def _updated_at(payload: dict[str, Any]) -> str:
        timestamp = payload.get("time_last_update_unix")
        if isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(timestamp, UTC).isoformat()
        value = payload.get("time_last_update_utc")
        if isinstance(value, str):
            try:
                return (
                    datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %z")
                    .astimezone(UTC)
                    .isoformat()
                )
            except ValueError:
                pass
        return datetime.now(UTC).isoformat()
