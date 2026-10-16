import hashlib
import hmac
import math
import secrets
from datetime import datetime
from typing import Any

from valutatrade_hub.core.exceptions import (
    InsufficientFundsError,
    InvalidPasswordError,
    WalletNotFoundError,
)
from valutatrade_hub.core.utils import validate_amount, validate_currency_code


class User:
    """Registered user with a salted password hash."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._user_id = int(user_id)
        self._username = username.strip()
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    def change_password(self, new_password: str) -> None:
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise InvalidPasswordError("Пароль должен быть не короче 4 символов")
        self._salt = secrets.token_hex(16)
        self._hashed_password = self._hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        return hmac.compare_digest(
            self._hashed_password, self._hash_password(password, self._salt)
        )

    def get_user_info(self) -> dict[str, Any]:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.get_user_info(),
            "hashed_password": self._hashed_password,
            "salt": self._salt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "User":
        date_value = data["registration_date"]
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=(
                datetime.fromisoformat(date_value)
                if isinstance(date_value, str)
                else date_value
            ),
        )

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        return hashlib.sha256(f"{password}{salt}".encode("utf-8")).hexdigest()


class Wallet:
    """Balance for one currency."""

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        self.currency_code = validate_currency_code(currency_code)
        self.balance = balance

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Баланс должен быть числом")
        numeric_value = float(value)
        if not math.isfinite(numeric_value) or numeric_value < 0:
            raise ValueError("Баланс должен быть конечным числом не меньше нуля")
        self._balance = numeric_value

    def deposit(self, amount: float) -> None:
        self.balance = self._balance + validate_amount(amount)

    def withdraw(self, amount: float) -> None:
        value = validate_amount(amount)
        if value > self._balance:
            raise InsufficientFundsError(
                f"Недостаточно средств: доступно {self._balance:.4f} "
                f"{self.currency_code}, требуется {value:.4f} {self.currency_code}"
            )
        self.balance = self._balance - value

    def get_balance_info(self) -> str:
        return f"{self.currency_code}: {self.balance:.4f}"

    def to_dict(self) -> dict[str, Any]:
        return {"currency_code": self.currency_code, "balance": self.balance}

    @classmethod
    def from_dict(cls, data: dict[str, Any], code: str | None = None) -> "Wallet":
        return cls(data.get("currency_code", code), data["balance"])


class Portfolio:
    """Collection of wallets owned by one user."""

    def __init__(
        self,
        user: User | None = None,
        wallets: dict[str, Wallet] | None = None,
        user_id: int | None = None,
    ) -> None:
        self._user = user
        self._user_id = user.user_id if user else user_id
        self._wallets = dict(wallets or {})

    @property
    def user(self) -> User | None:
        return self._user

    @property
    def user_id(self) -> int:
        if self._user_id is None:
            raise ValueError("Портфель не связан с пользователем")
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        return self._wallets.copy()

    def add_currency(self, currency_code: str) -> Wallet:
        code = validate_currency_code(currency_code)
        if code not in self._wallets:
            self._wallets[code] = Wallet(code)
        return self._wallets[code]

    def get_wallet(self, currency_code: str) -> Wallet:
        code = validate_currency_code(currency_code)
        try:
            return self._wallets[code]
        except KeyError as error:
            raise WalletNotFoundError(f"У вас нет кошелька '{code}'") from error

    def get_total_value(self, base_currency: str = "USD") -> float:
        from valutatrade_hub.core.usecases import get_rate

        base = validate_currency_code(base_currency)
        total = 0.0
        for code, wallet in self._wallets.items():
            total += wallet.balance * get_rate(code, base)["rate"]
        return total

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "wallets": {
                code: wallet.to_dict() for code, wallet in self._wallets.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], user: User | None = None) -> "Portfolio":
        wallets = {
            code: Wallet.from_dict(wallet_data, code)
            for code, wallet_data in data.get("wallets", {}).items()
        }
        return cls(user=user, wallets=wallets, user_id=data["user_id"])
