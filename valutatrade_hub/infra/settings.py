import tomllib
from pathlib import Path
from typing import Any

DEFAULT_DATA_FILENAMES = {
    "users": "users.json",
    "portfolios": "portfolios.json",
    "rates": "rates.json",
    "history": "exchange_rates.json",
}
DEFAULT_RATES_TTL_SECONDS = 300
DEFAULT_FIAT_RATES_TTL_SECONDS = 86400


class SettingsLoader:
    """Load and cache application settings from pyproject.toml."""

    _instance: "SettingsLoader | None" = None

    def __new__(cls) -> "SettingsLoader":
        """Return the process-wide settings loader instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Load the application settings once."""
        if getattr(self, "_initialized", False):
            return
        self._root = Path(__file__).resolve().parents[2]
        self._settings: dict[str, Any] = {}
        self._initialized = True
        self.reload()

    @property
    def root(self) -> Path:
        """Return the project root directory."""
        return self._root

    def get(self, key: str, default: Any = None) -> Any:
        """Return a configured value or its supplied default."""
        return self._settings.get(key, default)

    def reload(self) -> None:
        """Reload application settings from pyproject.toml."""
        config_path = self._root / "pyproject.toml"
        with config_path.open("rb") as config_file:
            data = tomllib.load(config_file)
        self._settings = data.get("tool", {}).get("valutatrade", {})


settings = SettingsLoader()
