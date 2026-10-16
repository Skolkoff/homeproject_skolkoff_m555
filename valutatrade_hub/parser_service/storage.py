import math
from datetime import UTC, datetime
from typing import Any

from valutatrade_hub.core.currencies import get_supported_currencies
from valutatrade_hub.core.exceptions import CurrencyNotFoundError
from valutatrade_hub.core.utils import validate_currency_code
from valutatrade_hub.infra.database import DatabaseManager


class RatesStorage:
    """Read current rates and persist updates with a rate history."""

    def __init__(self, database: DatabaseManager | None = None) -> None:
        self.database = database or DatabaseManager()

    def get_rates(self) -> dict[str, Any]:
        return self.database.load_rates()

    def save_update(self, new_rates: dict[str, dict[str, Any]]) -> int:
        current = self.database.load_rates()
        if not isinstance(current, dict):
            current = {"pairs": {}, "last_refresh": None}
        pairs = current.get("pairs")
        if not isinstance(pairs, dict):
            pairs = {}
            current["pairs"] = pairs
        history = self.database.load_history()
        if not isinstance(history, list):
            history = []
        history = [record for record in history if isinstance(record, dict)]
        history_ids = {
            record["id"] for record in history if isinstance(record.get("id"), str)
        }
        updated = 0

        for pair, data in new_rates.items():
            try:
                from_code, to_code = self._parse_pair(pair)
            except (AttributeError, CurrencyNotFoundError, ValueError):
                continue
            pair = f"{from_code}_{to_code}"
            if not isinstance(data, dict):
                continue
            rate = data.get("rate")
            if not self._valid_rate(rate):
                continue
            timestamp = data.get("updated_at")
            if not isinstance(timestamp, str):
                continue
            parsed_timestamp = self._parse_time(timestamp)
            if parsed_timestamp is None:
                continue
            previous = pairs.get(pair)
            if isinstance(previous, dict):
                previous_timestamp = self._parse_time(previous.get("updated_at"))
                if (
                    previous_timestamp is not None
                    and previous_timestamp >= parsed_timestamp
                ):
                    continue

            record = {
                "rate": float(rate),
                "updated_at": timestamp,
                "source": str(data.get("source", "Unknown")),
            }
            pairs[pair] = record
            history_record = {
                "id": f"{pair}_{timestamp}",
                "from_currency": from_code,
                "to_currency": to_code,
                "rate": float(rate),
                "timestamp": timestamp,
                "source": record["source"],
                "meta": data.get("meta", {}),
            }
            if history_record["id"] not in history_ids:
                history.append(history_record)
                history_ids.add(history_record["id"])
            updated += 1

        if updated:
            current["last_refresh"] = datetime.now(UTC).isoformat()
            self.database.save_rates(current)
            self.database.save_history(history)
        return updated

    def list_rates(
        self,
        currency: str | None = None,
        top: int | None = None,
        base: str = "USD",
    ) -> list[dict[str, Any]]:
        rates = self.get_rates().get("pairs", {})
        normalized_base = validate_currency_code(base)
        normalized_currency = validate_currency_code(currency) if currency else None
        crypto_codes = {
            code
            for code, metadata in get_supported_currencies().items()
            if metadata.kind == "CRYPTO"
        }
        rows = []

        valid_rates = {
            pair: data
            for pair, data in rates.items()
            if isinstance(pair, str)
            and isinstance(data, dict)
            and self._valid_rate(data.get("rate"))
        }
        for pair, data in valid_rates.items():
            try:
                from_code, to_code = self._parse_pair(pair)
            except (CurrencyNotFoundError, ValueError):
                continue
            if normalized_currency and normalized_currency not in (from_code, to_code):
                continue
            if top is not None and from_code not in crypto_codes:
                continue
            converted_rate = self._rate_between(valid_rates, from_code, normalized_base)
            if converted_rate is None:
                if to_code == normalized_base:
                    converted_rate = float(data["rate"])
                elif from_code == normalized_base:
                    converted_rate = 1.0 / float(data["rate"])
                else:
                    continue
            rows.append(
                {
                    "pair": f"{from_code}_{normalized_base}",
                    "rate": converted_rate,
                    "source": data.get("source", "Unknown"),
                    "updated_at": data.get("updated_at", "unknown"),
                }
            )

        unique_rows = {row["pair"]: row for row in rows}
        result = sorted(unique_rows.values(), key=lambda row: row["pair"])
        if top is not None:
            result = sorted(result, key=lambda row: row["rate"], reverse=True)[:top]
        return result

    @staticmethod
    def _parse_pair(pair: str) -> tuple[str, str]:
        parts = pair.split("_")
        if len(parts) != 2:
            raise ValueError(f"Некорректная пара валют: {pair}")
        return validate_currency_code(parts[0]), validate_currency_code(parts[1])

    @staticmethod
    def _parse_time(value: str) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed

    @staticmethod
    def _valid_rate(value: Any) -> bool:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        try:
            return math.isfinite(float(value)) and value > 0
        except OverflowError:
            return False

    @classmethod
    def _rate_between(
        cls, pairs: dict[str, dict[str, Any]], from_code: str, to_code: str
    ) -> float | None:
        if from_code == to_code:
            return 1.0
        direct = pairs.get(f"{from_code}_{to_code}")
        if direct:
            return float(direct["rate"])
        inverse = pairs.get(f"{to_code}_{from_code}")
        if inverse:
            return 1.0 / float(inverse["rate"])
        from_usd = cls._to_usd(pairs, from_code)
        to_usd = cls._to_usd(pairs, to_code)
        if from_usd is None or to_usd is None or to_usd == 0:
            return None
        return from_usd / to_usd

    @staticmethod
    def _to_usd(pairs: dict[str, dict[str, Any]], code: str) -> float | None:
        if code == "USD":
            return 1.0
        direct = pairs.get(f"{code}_USD")
        if direct:
            return float(direct["rate"])
        inverse = pairs.get(f"USD_{code}")
        if inverse:
            return 1.0 / float(inverse["rate"])
        return None
