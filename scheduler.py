"""
Планировщик ежедневной рассылки.
"""

import asyncio
import logging
import os
import random
import sqlite3
from datetime import datetime
from pathlib import Path

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

WISHES_FILE = Path(__file__).parent / "wishes.txt"


# ---------------------------------------------------------------------------
# Загрузка пожеланий из файла
# ---------------------------------------------------------------------------

def load_wishes() -> list[str]:
    with open(WISHES_FILE, encoding="utf-8") as f:
        wishes = [line.strip() for line in f if line.strip()]
    logger.info("Loaded %d wishes", len(wishes))
    return wishes


WISHES = load_wishes()


def get_fortune() -> str:
    return random.choice(WISHES)


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

async def broadcast():
    bot   = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    users = get_active_users()

    if not users:
        logger.info("No active users, skipping broadcast")
        return

    sent = 0
    for chat_id in users:
        text = get_fortune()
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
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
    logger.info("Starting broadcast for %s", datetime.now().strftime("%Y-%m-%d"))
    asyncio.run(broadcast())


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