import logging
from datetime import UTC, datetime
from typing import Any

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.storage import RatesStorage

_LOGGER = logging.getLogger("valutatrade.parser")


class RatesUpdater:
    """Fetch rates from configured clients and update local storage."""

    def __init__(
        self,
        clients: list[BaseApiClient] | None = None,
        storage: RatesStorage | None = None,
    ) -> None:
        self.clients = clients or [CoinGeckoClient(), ExchangeRateApiClient()]
        self.storage = storage or RatesStorage()

    def run_update(self, sources: set[str] | None = None) -> dict[str, Any]:
        _LOGGER.info("Starting rates update")
        collected: dict[str, dict[str, Any]] = {}
        errors = []
        for client in self.clients:
            source_key = (
                "coingecko"
                if client.source == "CoinGecko"
                else "exchangerate"
                if client.source == "ExchangeRate-API"
                else client.source.lower()
            )
            if sources is not None and source_key not in sources:
                continue
            try:
                client_rates = client.fetch_rates()
                collected.update(client_rates)
                _LOGGER.info(
                    "Fetched %s rates from %s", len(client_rates), client.source
                )
            except ApiRequestError as error:
                message = f"{client.source}: {error}"
                errors.append(message)
                _LOGGER.error("Failed to fetch from %s: %s", client.source, error)

        updated = self.storage.save_update(collected) if collected else 0
        last_refresh = self.storage.get_rates().get("last_refresh")
        if not last_refresh and updated:
            last_refresh = datetime.now(UTC).isoformat()
        _LOGGER.info("Rates update finished: %s updated", updated)
        return {
            "updated": updated,
            "errors": errors,
            "last_refresh": last_refresh,
        }
