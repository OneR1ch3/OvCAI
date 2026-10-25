import asyncio
import logging
import os
import re

from dotenv import load_dotenv
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

load_dotenv()

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION = os.environ["SESSION_STRING"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
SOURCE_CHAT_ID = int(os.environ["SOURCE_CHAT_ID"])
TARGET_CHAT_ID = int(os.environ["TARGET_CHAT_ID"])

TRIGGER_PREFIX = "🔔 У Вас новое сообщение!"
TRIGGER_BOT_USERNAME = "thevoprosybot"

TMP_DIR = "tmp"
MAX_PREVIEW_SIZE = 50 * 1024 * 1024  # файлы больше 50 МБ не скачиваем для предпросмотра
URL_RE = re.compile(r"(https?://|www\.|t\.me/|tg://)", re.IGNORECASE)

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("forwarder")

userbot = TelegramClient(StringSession(SESSION), API_ID, API_HASH)  # читает и публикует
bot = TelegramClient(StringSession(), API_ID, API_HASH)             # общается с тобой

os.makedirs(TMP_DIR, exist_ok=True)


def has_link(msg) -> bool:
    for e in msg.entities or []:
        if type(e).__name__ in ("MessageEntityUrl", "MessageEntityTextUrl"):
            return True
    return bool(URL_RE.search(msg.raw_text or ""))


async def send_to_moderation(msg, media: bool, link: bool):
    kinds = []
    if media:
        kinds.append("медиа")
    if link:
        kinds.append("ссылка")
    body = f"⚠️ На модерации ({', '.join(kinds)})\n\n{msg.raw_text or ''}"[:900]
    buttons = [[
        Button.inline("✅ Отправить", f"ok:{msg.id}".encode()),
        Button.inline("❌ Отклонить", f"no:{msg.id}".encode()),
    ]]

    path = None
    try:
        too_big = bool(msg.file and msg.file.size and msg.file.size > MAX_PREVIEW_SIZE)
        if media and not too_big:
            path = await msg.download_media(file=TMP_DIR + "/")
        if path:
            await bot.send_file(ADMIN_ID, path, caption=body, buttons=buttons)
        else:
            if media:
                body += "\n\n(предпросмотр недоступен)"
            await bot.send_message(ADMIN_ID, body, buttons=buttons, link_preview=False)
    except Exception:
        log.exception("Не удалось отправить на модерацию сообщение %s", msg.id)
    finally:
        if path and os.path.exists(path):
            os.remove(path)


@userbot.on(events.NewMessage(chats=SOURCE_CHAT_ID))
async def handler(event):
    msg = event.message
    text = msg.raw_text or ""

    starts_ok = TRIGGER_PREFIX in text[:60]
    sender = await event.get_sender()
    username = (getattr(sender, "username", None) or "").lower()
    from_bot_ok = username == TRIGGER_BOT_USERNAME
    if not (starts_ok or from_bot_ok):
        return

    media = bool(msg.media) and not msg.web_preview
    link = has_link(msg)

    if media or link:
        await send_to_moderation(msg, media, link)
        return

    if not text:
        return

    try:
        await userbot.send_message(
            TARGET_CHAT_ID,
            text,
            formatting_entities=msg.entities,
            link_preview=False,
        )
    except Exception:
        log.exception("Не удалось отправить сообщение %s", msg.id)


@bot.on(events.CallbackQuery(pattern=rb"^(ok|no):(\d+)$"))
async def on_decision(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("Нет доступа", alert=True)
        return

    action = event.pattern_match.group(1).decode()
    msg_id = int(event.pattern_match.group(2))

    if action == "ok":
        try:
            msg = await userbot.get_messages(SOURCE_CHAT_ID, ids=msg_id)
            if not msg:
                await event.answer("Сообщение не найдено (возможно, удалено)", alert=True)
                return
            await userbot.send_message(TARGET_CHAT_ID, msg)
            status = "✅ Отправлено в канал"
        except Exception:
            log.exception("Ошибка при публикации сообщения %s", msg_id)
            await event.answer("Ошибка при отправке, смотри логи", alert=True)
            return
    else:
        status = "❌ Отклонено"

    try:
        original = (await event.get_message()).raw_text or ""
        await event.edit(f"{status}\n\n{original}"[:1000], buttons=None)
    except Exception:
        log.exception("Не удалось обновить сообщение модерации")


async def main():
    await userbot.start()
    await userbot.get_dialogs()
    await bot.start(bot_token=BOT_TOKEN)
    await userbot.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
