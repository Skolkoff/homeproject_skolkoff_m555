# ValutaTrade Hub

ValutaTrade Hub — консольное приложение для виртуальной торговли валютами. В нём можно создать пользователя, посмотреть портфель, купить и продать валюту, а также получить курсы валют.

## Установка и запуск

Нужны Python 3.12 или новее и `uv`.

```bash
git clone https://github.com/Skolkoff/homeproject_skolkoff_m555.git
cd homeproject_skolkoff_m555
uv sync
uv run valutatrade
```

Приложение принимает команды в интерактивном режиме. Для выхода введите `exit`.

## API-ключ

Курсы криптовалют загружаются из CoinGecko. Для курсов фиатных валют нужен ключ ExchangeRate-API. Если файла `.env` ещё нет, создайте его из примера:

```bash
cp .env.example .env
```

```dotenv
EXCHANGERATE_API_KEY=ваш_ключ
```

Файл `.env` не добавляется в Git. Без ключа можно обновлять криптовалютные курсы командой `update-rates --source coingecko`.

## Команды

Зарегистрируйтесь и войдите:

```text
register --username demo --password 1234
login --username demo --password 1234
```

Посмотрите портфель, купите и продайте валюту:

```text
show-portfolio
buy --currency BTC --amount 0.001
sell --currency BTC --amount 0.0005
show-portfolio --base EUR
```

Посмотрите курсы и обновите кэш:

```text
get-rate --from EUR --to USD
show-rates
show-rates --currency BTC
show-rates --top 2
show-rates --base EUR
update-rates
update-rates --source coingecko
update-rates --source exchangerate
```

Для покупки используется виртуальный баланс USD. Продажа валюты начисляет выручку в USD. Если средств недостаточно, приложение сообщает об этом и не выполняет сделку.

## Данные и обновление курсов

Данные хранятся в JSON-файлах в папке `data/`:

- `users.json` — пользователи и хеши паролей;
- `portfolios.json` — кошельки и балансы;
- `rates.json` — последние курсы;
- `exchange_rates.json` — история обновлений курсов.

Папка и имена файлов настраиваются в секции `[tool.valutatrade]` файла `pyproject.toml`.

Курсы сохраняются в локальный кэш. Для криптовалют срок актуальности — 5 минут, для фиатных валют — 24 часа. Команда `get-rate` использует свежий кэш, а при необходимости запрашивает обновление у Parser Service. Команда `update-rates` обновляет курсы вручную.

## Структура проекта

```text
valutatrade_hub/
├── core/            # модели и бизнес-логика
├── infra/           # настройки и JSON-хранилище
├── parser_service/  # API-клиенты и обновление курсов
├── cli/             # команды приложения
├── decorators.py    # логирование действий
└── logging_config.py
data/                # файлы с данными приложения
main.py              # точка входа
```

## Демонстрация

[![Демонстрация ValutaTrade Hub](https://asciinema.org/a/ib2seliCTclnuAn5.svg)](https://asciinema.org/a/ib2seliCTclnuAn5)
