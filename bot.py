"""MAX support & feedback bot.

- Users can:
    * ask a question
    * propose a post (text / photo / video / file)
- Admin (configured via ADMIN_ID) can:
    * list open tickets
    * accept a ticket
    * reject a ticket with a reason
    * request edits with a comment
    * see simple stats
- All state is stored in a local SQLite database.

Built on aiogram 3 + aiosqlite.
Works for any Bot API-compatible messenger (Telegram, MAX, etc.).
"""

import asyncio
import logging
import sys
from contextlib import suppress

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from database import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("bot")


class UserFlow(StatesGroup):
    waiting_question = State()
    waiting_post_type = State()
    waiting_post_content = State()


def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Задать вопрос", callback_data="ask_question")],
        [InlineKeyboardButton(text="📝 Предложить пост", callback_data="propose_post")],
    ])


def post_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Текст", callback_data="post_type:text")],
        [InlineKeyboardButton(text="🖼 Фото", callback_data="post_type:photo")],
        [InlineKeyboardButton(text="🎥 Видео", callback_data="post_type:video")],
        [InlineKeyboardButton(text="📎 Файл", callback_data="post_type:file")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")],
    ])


def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_flow")],
    ])


def admin_ticket_kb(ticket_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"adm:accept:{ticket_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm:reject:{ticket_id}")],
        [InlineKeyboardButton(text="💬 Попросить правки", callback_data=f"adm:comment:{ticket_id}")],
    ])


def ticket_label(c: str) -> str:
    return {"question": "💬 Вопрос", "text": "✍️ Текст", "photo": "🖼 Фото",
            "video": "🎥 Видео", "file": "📎 Файл"}.get(c, c)


def short(t: str, limit: int = 200) -> str:
    if not t: return ""
    return t if len(t) <= limit else t[:limit-1] + "…"


user_router = Router()
admin_router = Router()


@user_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    db: Database = message.bot["db"]
    await db.upsert_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await message.answer("👋 Привет! Я бот поддержки.\n\nВыбери, что хочешь сделать:", reply_markup=main_menu_kb())


@user_router.callback_query(F.data == "ask_question")
async def on_ask(cb: CallbackQuery, state: FSMContext):
    await state.set_state(UserFlow.waiting_question)
    await cb.message.edit_text("✍️ Напиши свой вопрос — передам администратору.", reply_markup=cancel_kb())
    await cb.answer()


@user_router.callback_query(F.data == "propose_post")
async def on_propose(cb: CallbackQuery, state: FSMContext):
    await state.set_state(UserFlow.waiting_post_type)
    await cb.message.edit_text("📝 Какой тип поста предлагаешь?", reply_markup=post_type_kb())
    await cb.answer()


@user_router.callback_query(F.data == "back_main")
async def on_back(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("Главное меню:", reply_markup=main_menu_kb())
    await cb.answer()


@user_router.callback_query(F.data == "cancel_flow")
async def on_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("Отменено. Возвращаю в меню.", reply_markup=main_menu_kb())
    await cb.answer()


@user_router.message(UserFlow.waiting_question)
async def on_question(message: Message, state: FSMContext):
    db: Database = message.bot["db"]
    text = (message.text or "").strip()
    if not text:
        await message.answer("Кажется, пусто. Напиши вопрос текстом 🙂")
        return
    ticket_id = await db.create_ticket(message.from_user.id, "question", "text", text, None)
    await state.clear()
    await message.answer(f"✅ Спасибо! Твой вопрос принят.\nНомер заявки: #{ticket_id}", reply_markup=main_menu_kb())
    await notify_admin_new(message.bot, ticket_id)


@user_router.callback_query(UserFlow.waiting_post_type, F.data.startswith("post_type:"))
async def on_type(cb: CallbackQuery, state: FSMContext):
    chosen = cb.data.split(":", 1)[1]
    await state.update_data(post_type=chosen)
    await state.set_state(UserFlow.waiting_post_content)
    hints = {
        "text": "Отправь текст поста одним сообщением.",
        "photo": "Отправь фото (можно с подписью).",
        "video": "Отправь видео (можно с подписью).",
        "file": "Отправь файл как документ (можно с подписью).",
    }
    await cb.message.edit_text(f"📨 {hints[chosen]}", reply_markup=cancel_kb())
    await cb.answer()


@user_router.message(UserFlow.waiting_post_content)
async def on_post(message: Message, state: FSMContext):
    data = await state.get_data()
    chosen = data.get("post_type")
    db: Database = message.bot["db"]
    text = (message.caption or message.text or "").strip()
    file_id = None
    if chosen == "text":
        if message.content_type != ContentType.TEXT:
            await message.answer("Жду текст сообщением 🙂")
            return
    elif chosen == "photo":
        if not message.photo:
            await message.answer("Жду фото 📷")
            return
        file_id = message.photo[-1].file_id
    elif chosen == "video":
        if not message.video:
            await message.answer("Жду видео 🎥")
            return
        file_id = message.video.file_id
    elif chosen == "file":
        if not message.document:
            await message.answer("Жду файл как документ 📎")
            return
        file_id = message.document.file_id
    else:
        await message.answer("Что-то пошло не так. Возвращаю в меню.", reply_markup=main_menu_kb())
        await state.clear()
        return
    ticket_id = await db.create_ticket(message.from_user.id, "post", chosen, text, file_id)
    await state.clear()
    await message.answer(f"✅ Твоя заявка отправлена!\nНомер: #{ticket_id}", reply_markup=main_menu_kb())
    await notify_admin_new(message.bot, ticket_id, is_post=True)


@user_router.message()
async def on_fallback(message: Message):
    await message.answer("Выбери действие в меню:", reply_markup=main_menu_kb())


# ---------- admin ----------

async def notify_admin_new(bot: Bot, ticket_id: int, is_post: bool = False):
    db: Database = bot["db"]
    ticket = await db.get_ticket(ticket_id)
    if not ticket: return
    user = await db.get_user(ticket["user_id"])
    name = (user["full_name"] or user["username"] or "—") if user else "—"
    handle = f"@{user['username']}" if user and user["username"] else ""
    who = f"{name} {handle}".strip()
    header = "🆕 Новое предложение поста" if is_post else "📨 Новая заявка"
    body = (f"{header} #{ticket_id}\n"
            f"👤 {who}  (id: {ticket['user_id']})\n"
            f"📌 Тип: {ticket_label(ticket['content_type'])}\n")
    if ticket["text"]:
        body += f"\n💬 {short(ticket['text'])}\n"
    kb = admin_ticket_kb(ticket_id)
    try:
        if ticket["file_id"]:
            fk = ticket["content_type"]
            if fk == "photo":
                await bot.send_photo(config.ADMIN_ID, ticket["file_id"], caption=body, reply_markup=kb)
            elif fk == "video":
                await bot.send_video(config.ADMIN_ID, ticket["file_id"], caption=body, reply_markup=kb)
            elif fk == "file":
                await bot.send_document(config.ADMIN_ID, ticket["file_id"], caption=body, reply_markup=kb)
            else:
                await bot.send_message(config.ADMIN_ID, body, reply_markup=kb)
        else:
            await bot.send_message(config.ADMIN_ID, body, reply_markup=kb)
    except Exception:
        log.exception("Failed to notify admin about ticket %s", ticket_id)


async def notify_user(bot: Bot, ticket: dict, text: str):
    try:
        await bot.send_message(ticket["user_id"], text)
    except Exception:
        log.exception("Failed to notify user %s", ticket["user_id"])


@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != config.ADMIN_ID: return
    await message.answer("🔧 Админ-панель\n\n/list — открытые заявки\n/list all — все\n/stats — статистика\n/ticket <id> — детали")


@admin_router.message(Command("list"))
async def cmd_list(message: Message):
    if message.from_user.id != config.ADMIN_ID: return
    db: Database = message.bot["db"]
    args = (message.text or "").split()
    only_open = len(args) < 2 or args[1] != "all"
    tickets = await db.list_tickets(only_open=only_open, limit=20)
    if not tickets:
        await message.answer("Заявок нет ✅"); return
    lines = ["📋 Заявки:"]
    for t in tickets:
        em = {"open": "🟡", "accepted": "✅", "rejected": "❌", "commented": "💬"}.get(t["status"], "•")
        lines.append(f'{em} #{t["id"]}  {ticket_label(t["content_type"])}  id:{t["user_id"]}  [{t["status"]}]')
    await message.answer("\n".join(lines))


@admin_router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id != config.ADMIN_ID: return
    s = await message.bot["db"].stats()
    await message.answer(f"📊 Статистика:\nВсего: {s['total']}\nОткрытых: {s['open']}\nПринято: {s['accepted']}\nОтклонено: {s['rejected']}\nНа правках: {s['commented']}")


@admin_router.message(Command("ticket"))
async def cmd_ticket(message: Message):
    if message.from_user.id != config.ADMIN_ID: return
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("Использование: /ticket <id>"); return
    t = await message.bot["db"].get_ticket(int(args[1]))
    if not t:
        await message.answer("Не нашёл 🤷"); return
    body = f'🧾 Заявка #{t["id"]}\nСтатус: {t["status"]}\nТип: {ticket_label(t["content_type"])}\nЮзер: {t["user_id"]}\nСоздана: {t["created_at"]}\n'
    if t["text"]: body += f"\nТекст:\n{t['text']}\n"
    if t["admin_comment"]: body += f"\nКомментарий: {t['admin_comment']}\n"
    await message.answer(body, reply_markup=admin_ticket_kb(t["id"]))


@admin_router.callback_query(F.data.startswith("adm:"))
async def on_adm(cb: CallbackQuery, bot: Bot):
    if cb.from_user.id != config.ADMIN_ID:
        await cb.answer("Не для тебя 🙂", show_alert=True); return
    _, action, raw_id = cb.data.split(":")
    ticket_id = int(raw_id)
    db: Database = bot["db"]
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await cb.answer("Не найдено", show_alert=True); return
    if action == "accept":
        await db.set_status(ticket_id, "accepted")
        try: await cb.message.edit_text(f"{cb.message.text or ''}\n\n✅ Принято")
        except Exception: pass
        await notify_user(bot, ticket, "✅ Твоя заявка принята! Спасибо 🙌")
        await cb.answer("Принято")
    elif action == "reject":
        await cb.message.answer(f"Введи причину отказа для #{ticket_id} одним сообщением:")
        await cb.answer()
        pending = {"expect_from": cb.from_user.id, "action": "reject", "ticket_id": ticket_id}

        @admin_router.message(
            lambda m: m.from_user.id == pending["expect_from"]
            and (m.text or "").strip()
            and not (m.text or "").startswith("/")
        )
        async def collect_reason(message: Message):
            reason = (message.text or "").strip()
            await db.set_status(pending["ticket_id"], "rejected", reason)
            await message.answer(f"❌ Отклонено. Причина: {reason}")
            await notify_user(bot, ticket, f"❌ Твоя заявка #{pending['ticket_id']} отклонена.\nПричина: {reason}")
    elif action == "comment":
        await cb.message.answer(f"Введи комментарий / что поправить для #{ticket_id}:")
        await cb.answer()
        pending = {"expect_from": cb.from_user.id, "action": "comment", "ticket_id": ticket_id}

        @admin_router.message(
            lambda m: m.from_user.id == pending["expect_from"]
            and (m.text or "").strip()
            and not (m.text or "").startswith("/")
        )
        async def collect_comment(message: Message):
            comment = (message.text or "").strip()
            await db.set_status(pending["ticket_id"], "commented", comment)
            await message.answer(f"💬 Комментарий отправлен: {comment}")
            await notify_user(bot, ticket, f"💬 По заявке #{pending['ticket_id']} нужны правки:\n{comment}")


async def main():
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    db = Database(config.DATABASE_PATH)
    await db.init()
    bot["db"] = db
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(user_router)
    dp.include_router(admin_router)
    log.info("Starting bot…")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt, SystemExit):
        try: asyncio.run(main())
        except Exception: log.exception("Fatal error"); sys.exit(1)
