from threading import Event

from valutatrade_hub.parser_service.updater import RatesUpdater


def run_scheduler(
    interval_seconds: int,
    updater: RatesUpdater | None = None,
    stop_event: Event | None = None,
) -> None:
    """Refresh rates at a fixed interval until the stop event is set."""
    if interval_seconds < 1:
        raise ValueError("Интервал обновления должен быть больше нуля")
    service = updater or RatesUpdater()
    stop = stop_event or Event()
    while not stop.is_set():
        service.run_update()
        stop.wait(interval_seconds)
