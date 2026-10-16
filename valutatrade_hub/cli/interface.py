import argparse
import shlex
from typing import Any

from dotenv import load_dotenv
from prettytable import PrettyTable

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    NotLoggedInError,
    ValutaTradeError,
)
from valutatrade_hub.core.models import User
from valutatrade_hub.core.usecases import (
    buy,
    get_rate,
    login_user,
    register_user,
    sell,
    show_portfolio,
)
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import settings
from valutatrade_hub.logging_config import configure_logging
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="valutatrade")
    commands = parser.add_subparsers(dest="command", required=True)

    register = commands.add_parser("register", help="Создать пользователя")
    register.add_argument("--username", required=True)
    register.add_argument("--password", required=True)

    login = commands.add_parser("login", help="Войти в систему")
    login.add_argument("--username", required=True)
    login.add_argument("--password", required=True)

    portfolio = commands.add_parser("show-portfolio", help="Показать портфель")
    portfolio.add_argument("--base", default="USD")

    for name, description in (("buy", "Купить валюту"), ("sell", "Продать валюту")):
        trade = commands.add_parser(name, help=description)
        trade.add_argument("--currency", required=True)
        trade.add_argument("--amount", required=True, type=float)

    rate = commands.add_parser("get-rate", help="Получить курс")
    rate.add_argument("--from", dest="from_code", required=True)
    rate.add_argument("--to", dest="to_code", required=True)

    update = commands.add_parser("update-rates", help="Обновить курсы")
    update.add_argument("--source", choices=("coingecko", "exchangerate"))

    show_rates = commands.add_parser("show-rates", help="Показать курсы из кэша")
    show_rates.add_argument("--currency")
    show_rates.add_argument("--top", type=int)
    show_rates.add_argument("--base", default="USD")
    return parser


def main() -> None:
    """Start the interactive command line interface."""
    load_dotenv(settings.root / ".env")
    configure_logging()
    parser = _build_parser()
    current_user: User | None = None
    print("ValutaTrade Hub. Введите 'help' для списка команд или 'exit' для выхода.")

    while True:
        try:
            command_line = input("> ")
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания!")
            return
        if not command_line.strip():
            continue
        if command_line.strip() == "exit":
            print("До свидания!")
            return
        if command_line.strip() == "help":
            parser.print_help()
            continue
        try:
            arguments = parser.parse_args(shlex.split(command_line))
            current_user = _run_command(arguments, current_user)
        except SystemExit:
            continue
        except (ValutaTradeError, ValueError) as error:
            print(str(error))


def _run_command(arguments: argparse.Namespace, user: User | None) -> User | None:
    command = arguments.command
    if command == "register":
        created = register_user(arguments.username, arguments.password)
        print(
            f"Пользователь '{created.username}' "
            f"зарегистрирован (id={created.user_id}). "
            f"Войдите: login --username {created.username} --password ****"
        )
        return user

    if command == "login":
        logged_in = login_user(arguments.username, arguments.password)
        print(f"Вы вошли как '{logged_in.username}'")
        return logged_in

    if command == "update-rates":
        sources = {arguments.source} if arguments.source else None
        result = RatesUpdater().run_update(sources)
        if result["errors"]:
            print(f"Обновлено курсов: {result['updated']}")
            for error in result["errors"]:
                print(f"- {error}")
        else:
            print(
                f"Обновление завершено. Курсов: {result['updated']}; "
                f"время: {result['last_refresh'] or 'неизвестно'}"
            )
        return user

    if command == "show-rates":
        if arguments.top is not None and arguments.top < 1:
            raise ValueError("Параметр --top должен быть больше нуля")
        get_currency(arguments.base)
        if arguments.currency:
            get_currency(arguments.currency)
        database = DatabaseManager()
        storage = RatesStorage(database)
        rows = storage.list_rates(
            currency=arguments.currency,
            top=arguments.top,
            base=arguments.base,
        )
        if not rows:
            if database.load_rates().get("pairs"):
                raise CurrencyNotFoundError("Курсы по заданным условиям не найдены")
            raise ApiRequestError(
                "Локальный кеш курсов пуст. Выполните "
                "'update-rates', чтобы загрузить данные."
            )
        last_refresh = database.load_rates().get("last_refresh") or "неизвестно"
        print(f"Курсы из кэша (обновлено: {last_refresh}):")
        table = PrettyTable(["Пара", "Курс", "Источник", "Обновлено"])
        for row in rows:
            table.add_row(
                [row["pair"], f"{row['rate']:.8f}", row["source"], row["updated_at"]]
            )
        print(table)
        return user

    if command == "get-rate":
        rate_info = get_rate(arguments.from_code, arguments.to_code)
        rate_value = rate_info["rate"]
        print(
            f"Курс {rate_info['from_currency']}→{rate_info['to_currency']}: "
            f"{rate_value:.8f} (обновлено: {rate_info['updated_at']})"
        )
        print(
            f"Обратный курс {rate_info['to_currency']}→{rate_info['from_currency']}: "
            f"{1 / rate_value:.8f}"
        )
        return user

    if user is None:
        raise NotLoggedInError("Сначала выполните login")

    if command == "show-portfolio":
        portfolio, total = show_portfolio(user, arguments.base)
        print(f"Портфель пользователя '{user.username}' (база: {arguments.base}):")
        if not portfolio.wallets:
            print("Портфель пока пуст.")
            return user
        table = PrettyTable(["Валюта", "Баланс", f"Стоимость ({arguments.base})"])
        for code, wallet in portfolio.wallets.items():
            rate_info = get_rate(code, arguments.base)
            value = wallet.balance * rate_info["rate"]
            table.add_row([code, f"{wallet.balance:.4f}", f"{value:.2f}"])
        print(table)
        print(f"ИТОГО: {total:,.2f} {arguments.base}")
        return user

    if command in ("buy", "sell"):
        result: dict[str, Any]
        if command == "buy":
            result = buy(user, arguments.currency, arguments.amount)
            action = "Покупка"
        else:
            result = sell(user, arguments.currency, arguments.amount)
            action = "Продажа"
        print(f"{action} выполнена: {result['amount']:.4f} {result['currency_code']}")
        print(
            f"Изменения в портфеле: было {result['previous_balance']:.4f} → "
            f"стало {result['new_balance']:.4f} {result['currency_code']}"
        )
        label = "Стоимость покупки" if command == "buy" else "Выручка"
        print(
            f"{label}: {result['estimated_value']:,.2f} USD "
            f"(курс {result['rate']:.8f} USD/{result['currency_code']})"
        )
        print(
            f"USD: было {result['previous_cash_balance']:.2f} → "
            f"стало {result['cash_balance']:.2f}"
        )
        return user

    return user
