import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from valutatrade_hub.infra.settings import settings


def configure_logging() -> None:
    """Configure rotating logs for actions and parser updates."""
    log_dir = Path(settings.get("log_dir", "logs"))
    if not log_dir.is_absolute():
        log_dir = settings.root / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(levelname)s %(asctime)s %(message)s")

    for name, filename in (
        ("valutatrade.actions", "actions.log"),
        ("valutatrade.parser", "parser.log"),
    ):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if logger.handlers:
            continue
        handler = RotatingFileHandler(
            log_dir / filename,
            maxBytes=int(settings.get("log_max_bytes", 1_000_000)),
            backupCount=int(settings.get("log_backup_count", 3)),
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
