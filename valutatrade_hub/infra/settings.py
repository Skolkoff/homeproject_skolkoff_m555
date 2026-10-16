import tomllib
from pathlib import Path
from typing import Any


class SettingsLoader:
    """Load and cache application settings from pyproject.toml."""

    _instance: "SettingsLoader | None" = None

    def __new__(cls) -> "SettingsLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._root = Path(__file__).resolve().parents[2]
        self._settings: dict[str, Any] = {}
        self._initialized = True
        self.reload()

    @property
    def root(self) -> Path:
        return self._root

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def reload(self) -> None:
        config_path = self._root / "pyproject.toml"
        with config_path.open("rb") as config_file:
            data = tomllib.load(config_file)
        self._settings = data.get("tool", {}).get("valutatrade", {})


settings = SettingsLoader()
