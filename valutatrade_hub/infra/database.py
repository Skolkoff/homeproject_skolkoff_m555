import json
import os
import threading
from pathlib import Path
from typing import Any

from valutatrade_hub.core.exceptions import UsernameAlreadyExistsError
from valutatrade_hub.infra.settings import DEFAULT_DATA_FILENAMES, settings


class DatabaseManager:
    """Singleton JSON storage for users, portfolios, and rates."""

    _instance: "DatabaseManager | None" = None

    def __new__(cls) -> "DatabaseManager":
        """Return the process-wide database manager instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Prepare storage paths and the shared access lock."""
        if getattr(self, "_initialized", False):
            return
        data_path = Path(settings.get("data_dir", "data"))
        self.data_dir = (
            data_path if data_path.is_absolute() else settings.root / data_path
        )
        self._files = {
            key: settings.get(f"{key}_filename", default)
            for key, default in DEFAULT_DATA_FILENAMES.items()
        }
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialized = True

    def load_users(self) -> list[dict[str, Any]]:
        """Load all saved user records."""
        return self._read(self._files["users"], [])

    def save_users(self, users: list[dict[str, Any]]) -> None:
        """Save all user records."""
        self._write(self._files["users"], users)

    def save_registration(
        self,
        username: str,
        user_record: dict[str, Any],
        portfolio_record: dict[str, Any],
    ) -> None:
        """Save a new user and portfolio as one registration operation."""
        with self._lock:
            users = self.load_users()
            if any(
                item.get("username", "").casefold() == username.casefold()
                for item in users
            ):
                raise UsernameAlreadyExistsError(
                    f"Имя пользователя '{username}' уже занято"
                )
            portfolios = self.load_portfolios()
            users.append(user_record)
            portfolios.append(portfolio_record)
            self._write_many(
                {
                    self._files["users"]: users,
                    self._files["portfolios"]: portfolios,
                }
            )

    def load_portfolios(self) -> list[dict[str, Any]]:
        """Load all saved portfolios."""
        return self._read(self._files["portfolios"], [])

    def save_portfolios(self, portfolios: list[dict[str, Any]]) -> None:
        """Save all portfolios."""
        self._write(self._files["portfolios"], portfolios)

    def load_rates(self) -> dict[str, Any]:
        """Load the latest cached exchange rates."""
        data = self._read(self._files["rates"], {"pairs": {}, "last_refresh": None})
        if not isinstance(data, dict):
            return {"pairs": {}, "last_refresh": None}
        if "pairs" not in data or not isinstance(data.get("pairs"), dict):
            legacy_data = data
            data = {"pairs": {}, "last_refresh": legacy_data.get("last_refresh")}
            for key, value in legacy_data.items():
                if isinstance(value, dict) and "rate" in value:
                    data["pairs"][key] = value
        return data

    def save_rates(self, rates: dict[str, Any]) -> None:
        """Save the current exchange-rate cache."""
        self._write(self._files["rates"], rates)

    def load_history(self) -> list[dict[str, Any]]:
        """Load the exchange-rate update history."""
        return self._read(self._files["history"], [])

    def save_history(self, history: list[dict[str, Any]]) -> None:
        """Save the exchange-rate update history."""
        self._write(self._files["history"], history)

    def _read(self, filename: str, default: Any) -> Any:
        path = self.data_dir / filename
        with self._lock:
            if not path.exists():
                self._write(filename, default)
                return default
            try:
                with path.open(encoding="utf-8") as data_file:
                    return json.load(data_file)
            except json.JSONDecodeError as error:
                raise ValueError(f"Файл данных повреждён: {path.name}") from error

    def _write(self, filename: str, data: Any) -> None:
        path = self.data_dir / filename
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with self._lock:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with temp_path.open("w", encoding="utf-8") as data_file:
                json.dump(data, data_file, ensure_ascii=False, indent=2)
                data_file.write("\n")
                data_file.flush()
                os.fsync(data_file.fileno())
            os.replace(temp_path, path)

    def _write_many(self, values: dict[str, Any]) -> None:
        temp_paths: dict[str, Path] = {}
        old_values = {
            filename: (self.data_dir / filename).read_bytes()
            if (self.data_dir / filename).exists()
            else None
            for filename in values
        }
        replaced: list[str] = []
        try:
            for filename, value in values.items():
                path = self.data_dir / filename
                temp_path = path.with_suffix(path.suffix + ".tmp")
                with temp_path.open("w", encoding="utf-8") as data_file:
                    json.dump(value, data_file, ensure_ascii=False, indent=2)
                    data_file.write("\n")
                    data_file.flush()
                    os.fsync(data_file.fileno())
                temp_paths[filename] = temp_path
            for filename, temp_path in temp_paths.items():
                os.replace(temp_path, self.data_dir / filename)
                replaced.append(filename)
        except OSError:
            for filename in reversed(replaced):
                path = self.data_dir / filename
                previous = old_values[filename]
                if previous is None:
                    path.unlink(missing_ok=True)
                else:
                    rollback_path = path.with_suffix(path.suffix + ".rollback")
                    rollback_path.write_bytes(previous)
                    os.replace(rollback_path, path)
            raise
        finally:
            for temp_path in temp_paths.values():
                temp_path.unlink(missing_ok=True)
