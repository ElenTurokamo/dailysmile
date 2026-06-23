"""
Планировщик ежедневной рассылки.
"""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime

from google import genai
import schedule
import time
from telegram import Bot
from telegram.error import Forbidden, TelegramError

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DB_PATH   = os.getenv("DB_PATH", "users.db")
SEND_TIME = os.getenv("SEND_TIME", "06:00")


# ---------------------------------------------------------------------------
# Генерация одной печеньки на весь день
# ---------------------------------------------------------------------------

def generate_fortune() -> str:
    client = genai.Client(api_key=os.environ["AI_API_KEY"])
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=(
            "Ты — тёплый утренний друг, который помогает начать день с улыбкой. "
            "Напиши одно короткое утреннее пожелание или вдохновляющую мысль на день "
            "(2–4 предложения, не более 200 символов). "
            "Тон: бодрый, тёплый, искренний — как сообщение от близкого человека. "
            "Язык: русский. Начни сразу с текста, без вводных слов."
        ),
    )
    return response.text.strip()


# ---------------------------------------------------------------------------
# Получение активных пользователей
# ---------------------------------------------------------------------------

def get_active_users() -> list[int]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT chat_id FROM users WHERE active = 1"
    ).fetchall()
    conn.close()
    return [row[0] for row in rows]


def deactivate_user(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE users SET active = 0 WHERE chat_id = ?",
        (chat_id,),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Рассылка
# ---------------------------------------------------------------------------

async def broadcast(fortune: str):
    bot   = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    users = get_active_users()

    if not users:
        logger.info("No active users, skipping broadcast")
        return

    text = f"{fortune}"

    sent = 0
    for chat_id in users:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
            )
            sent += 1
        except Forbidden:
            logger.warning("User %s blocked the bot — deactivating", chat_id)
            deactivate_user(chat_id)
        except TelegramError as e:
            logger.error("Failed to send to %s: %s", chat_id, e)

    logger.info("Broadcast done: %d/%d sent", sent, len(users))


# ---------------------------------------------------------------------------
# Ежедневная задача
# ---------------------------------------------------------------------------

def daily_job():
    logger.info("Generating fortune for %s", datetime.now().strftime("%Y-%m-%d"))

    try:
        fortune = generate_fortune()
        logger.info("Fortune: %s", fortune)
    except Exception as e:
        logger.error("Failed to generate fortune: %s", e)
        return

    asyncio.run(broadcast(fortune))


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main():
    logger.info("Scheduler started. Will send at %s every day.", SEND_TIME)
    schedule.every().day.at(SEND_TIME).do(daily_job)

    if os.getenv("RUN_ON_START", "false").lower() == "true":
        logger.info("RUN_ON_START=true — running daily_job now")
        daily_job()

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()