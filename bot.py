import logging
import sqlite3
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "users.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id  INTEGER PRIMARY KEY,
            username TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active    INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()


def get_db():
    return sqlite3.connect(DB_PATH)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id  = update.effective_chat.id
    username = update.effective_user.username or ""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO users (chat_id, username)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET active = 1
        """, (chat_id, username))
    await update.message.reply_text(
        "☀️ *Привет! Твоё утро начинается здесь.*\n\n"
        "Каждое утро в 6:00 я буду присылать тебе заряд хорошего настроения — "
        "улыбку, с которой легче начать день.\n\n"
        "Отключить рассылку — /stop",
        parse_mode="Markdown",
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET active = 0 WHERE chat_id = ?",
            (chat_id,),
        )
    await update.message.reply_text(
        "😴 Хорошо, утренние сообщения отключены.\n"
        "Захочешь вернуться — просто напиши /start"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with get_db() as conn:
        row = conn.execute(
            "SELECT active, joined_at FROM users WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    if row is None:
        await update.message.reply_text(
            "☀️ Ты ещё не с нами! Напиши /start — и утро заиграет новыми красками."
        )
    elif row[0] == 1:
        await update.message.reply_text(
            f"🌤 Всё отлично! Утренние улыбки уже летят к тебе.\n"
            f"С нами с: {row[1][:10]} 🗓"
        )
    else:
        await update.message.reply_text(
            "🌙 Пока отдыхаешь от утренних сообщений.\n"
            "Готов начать день с улыбкой? Возобновить: /start"
        )


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]

    init_db()

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("stop",   stop))
    app.add_handler(CommandHandler("status", status))

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
