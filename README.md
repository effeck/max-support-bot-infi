# MAX Support & Feedback Bot

Бот для приёма обращений в поддержку и предложений постов от пользователей. Работает в MAX и в Telegram (Bot API у них совместим).

## Что умеет

👤 **Пользователь:**
- 💬 Задать вопрос
- 📝 Предложить пост: текст / фото / видео / файл
- Получить ответ админа (принято / отклонено с причиной / нужны правки)

🛠 **Админ (только `ADMIN_ID`):**
- `/list` — открытые заявки
- `/list all` — все заявки
- `/ticket <id>` — подробности по заявке
- `/stats` — статистика
- В каждой заявке — три кнопки: **Принять / Отклонить / Попросить правки**
- При отклонении/правках бот попросит ввести причину одним сообщением

## Стек

- Python 3.10+
- [aiogram 3](https://docs.aiogram.dev/)
- [aiosqlite](https://github.com/omnilib/aiosqlite)
- SQLite

## Структура

```
├── bot.py            # логика бота, FSM, роутеры
├── database.py       # слой работы с SQLite
├── config.py         # загрузка настроек из .env
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Установка и запуск

```bash
git clone https://github.com/effeck/max-support-bot-infi.git
cd max-support-bot-infi
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# отредактируй .env: впиши BOT_TOKEN и ADMIN_ID
python bot.py
```

## Токен

- **MAX**: в @MasterBot создай бота → скопируй токен
- **Telegram**: в @BotFather → `/newbot`

## Свой ADMIN_ID

- **Telegram**: напиши [@userinfobot](https://t.me/userinfobot)
- **MAX**: создай бота, отправь ему `/start`, и в логах при первом запуске увидишь `user.id` (мы логируем входящие апдейты)

## Деплой (VPS)

```ini
# /etc/systemd/system/max-bot.service
[Unit]
Description=MAX Support Bot
After=network.target

[Service]
WorkingDirectory=/opt/max-support-bot-infi
ExecStart=/opt/max-support-bot-infi/.venv/bin/python bot.py
Restart=always
EnvironmentFile=/opt/max-support-bot-infi/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now max-bot
sudo journalctl -u max-bot -f
```

## Тонкая настройка

- **Parse mode HTML** — если MAX не поддерживает, замени в `bot.py`:
  `default=DefaultBotProperties(parse_mode=ParseMode.HTML)` → `parse_mode=None`
- **Группа вместо лички** — замени `ADMIN_ID` на id группы
- **Несколько админов** — расширь `config.py` до `ADMIN_IDS = [...]` и проверяй `in config.ADMIN_IDS`

## Лицензия

MIT
