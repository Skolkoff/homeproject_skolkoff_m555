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
from valutatrade_hub.core.utils import (
    MIN_PASSWORD_LENGTH,
    validate_amount,
    validate_currency_code,
)


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
        """Create a user model from its identity and password record."""
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._user_id = int(user_id)
        self._username = username.strip()
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @property
    def user_id(self) -> int:
        """Return the user's unique identifier."""
        return self._user_id

    @property
    def username(self) -> str:
        """Return the user's display name."""
        return self._username

    @property
    def hashed_password(self) -> str:
        """Return the stored password hash."""
        return self._hashed_password

    @property
    def salt(self) -> str:
        """Return the salt used for the password hash."""
        return self._salt

    @property
    def registration_date(self) -> datetime:
        """Return the user's registration date."""
        return self._registration_date

    def change_password(self, new_password: str) -> None:
        """Replace the password hash using a newly generated salt."""
        if not isinstance(new_password, str) or len(new_password) < MIN_PASSWORD_LENGTH:
            raise InvalidPasswordError(
                f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов"
            )
        self._salt = secrets.token_hex(16)
        self._hashed_password = self._hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        """Check whether a password matches the stored hash."""
        return hmac.compare_digest(
            self._hashed_password, self._hash_password(password, self._salt)
        )

    def get_user_info(self) -> dict[str, Any]:
        """Return public user details without password data."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the user for JSON storage."""
        return {
            **self.get_user_info(),
            "hashed_password": self._hashed_password,
            "salt": self._salt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "User":
        """Create a user from a stored JSON record."""
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
        """Create a wallet for one currency with an optional balance."""
        self.currency_code = validate_currency_code(currency_code)
        self.balance = balance

    @property
    def balance(self) -> float:
        """Return the current wallet balance."""
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        """Set the balance to a finite, non-negative number."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Баланс должен быть числом")
        numeric_value = float(value)
        if not math.isfinite(numeric_value) or numeric_value < 0:
            raise ValueError("Баланс должен быть конечным числом не меньше нуля")
        self._balance = numeric_value

    def deposit(self, amount: float) -> None:
        """Add a positive amount to the wallet."""
        self.balance = self._balance + validate_amount(amount)

    def withdraw(self, amount: float) -> None:
        """Remove a positive amount when the wallet can cover it."""
        value = validate_amount(amount)
        if value > self._balance:
            raise InsufficientFundsError(
                f"Недостаточно средств: доступно {self._balance:.4f} "
                f"{self.currency_code}, требуется {value:.4f} {self.currency_code}"
            )
        self.balance = self._balance - value

    def get_balance_info(self) -> str:
        """Return a short text summary of the wallet balance."""
        return f"{self.currency_code}: {self.balance:.4f}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize the wallet for JSON storage."""
        return {"currency_code": self.currency_code, "balance": self.balance}

    @classmethod
    def from_dict(cls, data: dict[str, Any], code: str | None = None) -> "Wallet":
        """Create a wallet from a stored JSON record."""
        return cls(data.get("currency_code", code), data["balance"])


class Portfolio:
    """Collection of wallets owned by one user."""

    def __init__(
        self,
        user: User | None = None,
        wallets: dict[str, Wallet] | None = None,
        user_id: int | None = None,
    ) -> None:
        """Create a portfolio for a user with optional existing wallets."""
        self._user = user
        self._user_id = user.user_id if user else user_id
        self._wallets = dict(wallets or {})

    @property
    def user(self) -> User | None:
        """Return the owner of the portfolio, when available."""
        return self._user

    @property
    def user_id(self) -> int:
        """Return the portfolio owner's identifier."""
        if self._user_id is None:
            raise ValueError("Портфель не связан с пользователем")
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Return a copy of the portfolio's wallet mapping."""
        return self._wallets.copy()

    def add_currency(self, currency_code: str) -> Wallet:
        """Return the wallet for a currency, creating it when needed."""
        code = validate_currency_code(currency_code)
        if code not in self._wallets:
            self._wallets[code] = Wallet(code)
        return self._wallets[code]

    def get_wallet(self, currency_code: str) -> Wallet:
        """Return an existing wallet for a currency."""
        code = validate_currency_code(currency_code)
        try:
            return self._wallets[code]
        except KeyError as error:
            raise WalletNotFoundError(f"У вас нет кошелька '{code}'") from error

    def get_total_value(self, base_currency: str = "USD") -> float:
        """Convert all wallet balances to the selected base currency."""
        from valutatrade_hub.core.usecases import get_rate

        base = validate_currency_code(base_currency)
        total = 0.0
        for code, wallet in self._wallets.items():
            total += wallet.balance * get_rate(code, base)["rate"]
        return total

    def to_dict(self) -> dict[str, Any]:
        """Serialize the portfolio for JSON storage."""
        return {
            "user_id": self.user_id,
            "wallets": {
                code: wallet.to_dict() for code, wallet in self._wallets.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], user: User | None = None) -> "Portfolio":
        """Create a portfolio from a stored JSON record."""
        wallets = {
            code: Wallet.from_dict(wallet_data, code)
            for code, wallet_data in data.get("wallets", {}).items()
        }
        return cls(user=user, wallets=wallets, user_id=data["user_id"])
