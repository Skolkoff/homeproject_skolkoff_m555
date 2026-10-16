from datetime import UTC, datetime
from typing import Any

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    InvalidPasswordError,
    UsernameAlreadyExistsError,
    UserNotFoundError,
)
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import validate_amount
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import settings
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater


def _database() -> DatabaseManager:
    return DatabaseManager()


def _users() -> list[User]:
    return [User.from_dict(item) for item in _database().load_users()]


def _portfolio_for(user: User) -> Portfolio:
    records = _database().load_portfolios()
    for record in records:
        if record.get("user_id") == user.user_id:
            return Portfolio.from_dict(record, user)
    return Portfolio(user=user)


def _save_portfolio(portfolio: Portfolio) -> None:
    database = _database()
    records = database.load_portfolios()
    updated = False
    for index, record in enumerate(records):
        if record.get("user_id") == portfolio.user_id:
            records[index] = portfolio.to_dict()
            updated = True
            break
    if not updated:
        records.append(portfolio.to_dict())
    database.save_portfolios(records)


@log_action("REGISTER")
def register_user(username: str, password: str) -> User:
    """Create a salted user record and an empty portfolio."""
    normalized_name = username.strip() if isinstance(username, str) else ""
    if not normalized_name:
        raise ValueError("Имя пользователя не может быть пустым")
    if not isinstance(password, str) or len(password) < 4:
        raise InvalidPasswordError("Пароль должен быть не короче 4 символов")
    users = _users()
    if any(user.username.casefold() == normalized_name.casefold() for user in users):
        raise UsernameAlreadyExistsError(
            f"Имя пользователя '{normalized_name}' уже занято"
        )

    user_id = max((user.user_id for user in users), default=0) + 1
    user = User(
        user_id=user_id,
        username=normalized_name,
        hashed_password="",
        salt="",
        registration_date=datetime.now(UTC),
    )
    user.change_password(password)
    starting_balance = float(settings.get("starting_balance_usd", 10000.0))
    if starting_balance < 0:
        raise ValueError("Начальный баланс не может быть отрицательным")
    portfolio = Portfolio(user=user)
    if starting_balance > 0:
        portfolio.add_currency("USD").balance = starting_balance
    _database().save_registration(
        normalized_name,
        user.to_dict(),
        portfolio.to_dict(),
    )
    return user


@log_action("LOGIN")
def login_user(username: str, password: str) -> User:
    """Authenticate a user and return the current user model."""
    user = next((item for item in _users() if item.username == username), None)
    if user is None:
        raise UserNotFoundError(f"Пользователь '{username}' не найден")
    if not user.verify_password(password):
        raise InvalidPasswordError("Неверный пароль")
    return user


def show_portfolio(user: User, base_currency: str = "USD") -> tuple[Portfolio, float]:
    """Return a user's portfolio and total value in the selected base."""
    get_currency(base_currency)
    portfolio = _portfolio_for(user)
    total = sum(
        wallet.balance * get_rate(code, base_currency)["rate"]
        for code, wallet in portfolio.wallets.items()
    )
    return portfolio, total


@log_action("BUY", verbose=True)
def buy(user: User, currency_code: str, amount: float) -> dict[str, Any]:
    """Buy a positive amount of a supported currency with virtual USD."""
    code = get_currency(currency_code).code
    if code == "USD":
        raise ValueError("USD используется для расчётов и не покупается отдельно")
    value = validate_amount(amount)
    rate_info = get_rate(code, "USD")
    rate = rate_info["rate"]
    cost = value * rate
    portfolio = _portfolio_for(user)
    wallet = portfolio.add_currency(code)
    cash_wallet = portfolio.add_currency("USD")
    previous_balance = wallet.balance
    previous_cash_balance = cash_wallet.balance
    cash_wallet.withdraw(cost)
    wallet.deposit(value)
    _save_portfolio(portfolio)
    return {
        "currency_code": code,
        "amount": value,
        "previous_balance": previous_balance,
        "new_balance": wallet.balance,
        "rate": rate,
        "base": "USD",
        "estimated_value": cost,
        "previous_cash_balance": previous_cash_balance,
        "cash_balance": cash_wallet.balance,
    }


@log_action("SELL", verbose=True)
def sell(user: User, currency_code: str, amount: float) -> dict[str, Any]:
    """Sell a positive amount of a supported currency for virtual USD."""
    code = get_currency(currency_code).code
    if code == "USD":
        raise ValueError("USD является базовой валютой и не продаётся отдельно")
    value = validate_amount(amount)
    portfolio = _portfolio_for(user)
    wallet = portfolio.get_wallet(code)
    previous_balance = wallet.balance
    rate = get_rate(code, "USD")["rate"]
    proceeds = value * rate
    cash_wallet = portfolio.add_currency("USD")
    previous_cash_balance = cash_wallet.balance
    wallet.withdraw(value)
    cash_wallet.deposit(proceeds)
    _save_portfolio(portfolio)
    return {
        "currency_code": code,
        "amount": value,
        "previous_balance": previous_balance,
        "new_balance": wallet.balance,
        "rate": rate,
        "base": "USD",
        "estimated_value": proceeds,
        "previous_cash_balance": previous_cash_balance,
        "cash_balance": cash_wallet.balance,
    }


def get_rate(from_code: str, to_code: str) -> dict[str, Any]:
    """Return a fresh direct or cross rate, updating the cache if needed."""
    source = get_currency(from_code).code
    target = get_currency(to_code).code
    if source == target:
        return {
            "from_currency": source,
            "to_currency": target,
            "rate": 1.0,
            "updated_at": datetime.now(UTC).isoformat(),
            "source": "identity",
        }

    storage = RatesStorage()
    cached = _get_fresh_cached_rate(storage, source, target)
    if cached is not None:
        return cached

    update = RatesUpdater(storage=storage).run_update()
    cached = _get_fresh_cached_rate(storage, source, target)
    if cached is not None:
        return cached

    details = "; ".join(update["errors"])
    suffix = f" ({details})" if details else ""
    raise ApiRequestError(
        f"Курс {source}→{target} недоступен или устарел. "
        f"Выполните update-rates и повторите попытку{suffix}"
    )


def _get_fresh_cached_rate(
    storage: RatesStorage, from_code: str, to_code: str
) -> dict[str, Any] | None:
    pairs = storage.get_rates().get("pairs", {})
    rate = RatesStorage._rate_between(pairs, from_code, to_code)
    if rate is None:
        return None

    contributing_codes = {from_code, to_code}
    pair_records = []
    for code in contributing_codes:
        if code == "USD":
            continue
        direct = pairs.get(f"{code}_USD")
        inverse = pairs.get(f"USD_{code}")
        pair_record = direct or inverse
        if pair_record is None:
            return None
        if not _is_fresh(pair_record, code):
            return None
        pair_records.append(pair_record)

    direct_record = pairs.get(f"{from_code}_{to_code}")
    if direct_record and _is_fresh(direct_record, from_code):
        selected = direct_record
    elif pair_records:
        selected = min(pair_records, key=lambda item: _timestamp(item["updated_at"]))
    else:
        return None
    return {
        "from_currency": from_code,
        "to_currency": to_code,
        "rate": rate,
        "updated_at": selected["updated_at"],
        "source": selected.get("source", "local cache"),
    }


def _is_fresh(record: dict[str, Any], code: str) -> bool:
    age = (datetime.now(UTC) - _timestamp(record["updated_at"])).total_seconds()
    is_crypto = get_currency(code).kind == "CRYPTO"
    ttl_key = "rates_ttl_seconds" if is_crypto else "fiat_rates_ttl_seconds"
    default_ttl = 300 if is_crypto else 86400
    return age <= int(settings.get(ttl_key, default_ttl))


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
