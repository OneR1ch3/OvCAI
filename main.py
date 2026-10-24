import asyncio
import logging
import os

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

load_dotenv()

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SOURCE_CHAT_ID = int(os.environ["SOURCE_CHAT_ID"])
TARGET_CHAT_ID = int(os.environ["TARGET_CHAT_ID"])
SESSION = os.environ["SESSION_STRING"]

TRIGGER_PREFIX = "🔔 У Вас новое сообщение!"
TRIGGER_BOT_USERNAME = "thevoprosybot"

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("forwarder")

client = TelegramClient("userbot_session", API_ID, API_HASH)
client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)


@client.on(events.NewMessage(chats=SOURCE_CHAT_ID))
async def handler(event):
    msg = event.message

    if not msg.raw_text:
        return
    if msg.media and not msg.web_preview:
        return

    starts_ok = TRIGGER_PREFIX in msg.raw_text[:60]

    sender = await event.get_sender()
    username = (getattr(sender, "username", None) or "").lower()
    from_bot_ok = username == TRIGGER_BOT_USERNAME

    if not (starts_ok or from_bot_ok):
        return

    try:
        await client.send_message(
            TARGET_CHAT_ID,
            msg.raw_text,
            formatting_entities=msg.entities,
            link_preview=False,
        )
    except Exception:
        log.exception("Не удалось отправить сообщение %s", msg.id)


async def main():
    await client.start()
    await client.get_dialogs()
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())