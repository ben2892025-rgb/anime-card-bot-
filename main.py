
import os
import re
import random
import sqlite3

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ========== SETTINGS ==========

BOT_TOKEN = os.getenv("BOT_TOKEN", "9074669214:AAG7B-xyrKbCagLyL_nndfngL1yk9HO8ixk")
OWNER_ID = int(os.getenv("OWNER_ID", "8709989912"))

CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "")

DB = sqlite3.connect("anime_cards.db", check_same_thread=False)
DB.row_factory = sqlite3.Row

RARITIES = [
    "Common",
    "Uncommon",
    "Rare",
    "Super Rare",
    "Epic",
    "Legendary",
    "Mythic",
    "Divine",
    "Celestial",
    "Eternal",
    "Transcendent"
]

# Rarity drop chances (total 100)
WEIGHTS = [35, 22, 15, 10, 7, 4, 2.8, 1.5, 1, 0.5, 0.2]

# ========== DATABASE ==========

DB.execute("""
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    file_id TEXT NOT NULL,
    file_unique_id TEXT NOT NULL,
    rarity TEXT NOT NULL
)
""")

DB.execute("""
CREATE TABLE IF NOT EXISTS collections (
    user_id INTEGER,
    card_id INTEGER,
    quantity INTEGER DEFAULT 1,
    PRIMARY KEY(user_id, card_id)
)
""")

DB.execute("""
CREATE TABLE IF NOT EXISTS group_counts (
    chat_id INTEGER PRIMARY KEY,
    word_count INTEGER DEFAULT 0
)
""")

DB.execute("""
CREATE TABLE IF NOT EXISTS pending (
    chat_id INTEGER PRIMARY KEY,
    card_id INTEGER
)
""")

DB.commit()


# ========== HELPERS ==========

def is_owner(user_id):
    return user_id == OWNER_ID and OWNER_ID != 0


def get_random_card():
    return DB.execute(
        "SELECT * FROM cards ORDER BY RANDOM() LIMIT 1"
    ).fetchone()


def rarity_random():
    return random.choices(RARITIES, weights=WEIGHTS, k=1)[0]


async def send_drop(chat_id, context):
    card = get_random_card()

    if not card:
        await context.bot.send_message(
            chat_id,
            "❌ ကတ်မရှိသေးပါ။ Owner က ကတ်အသစ်ထည့်ပေးပါ။"
        )
        return

    rarity = card["rarity"]

    DB.execute(
        "INSERT OR REPLACE INTO pending(chat_id, card_id) VALUES (?, ?)",
        (chat_id, card["id"])
    )
    DB.commit()

    await context.bot.send_photo(
        chat_id=chat_id,
        photo=card["file_id"],
        caption=(
            f"🎴 A CHARACTER HAS APPEARED!\n\n"
            f"💎 Rarity: {rarity}\n"
            f"🔢 CARD ID: #{card['id']}\n\n"
            f"ဖမ်းချင်ရင် /catch နှိပ်ပါ။"
        )
    )


async def check_channel(user_id, context):
    if not CHANNEL_USERNAME:
        return True

    try:
        member = await context.bot.get_chat_member(
            CHANNEL_USERNAME, user_id
        )
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


# ========== START ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎴 WELCOME TO ANIME CARD BOT!\n\n"
        "Commands:\n"
        "/catch - Catch a card\n"
        "/collection - My cards\n"
        "/w - Find card name\n\n"
        "ကတ်တွေ စုဆောင်းကြည့်ပါ။ 💎"
    )


# ========== ADD CARD ==========

async def addcard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not is_owner(user.id):
        return

    msg = update.message

    if not msg.reply_to_message or not msg.reply_to_message.photo:
        await msg.reply_text(
            "ကတ်ပုံကို Reply လုပ်ပြီး ဒီလိုရေးပါ။\n"
            "/addcard Character Name | Rarity\n\n"
            "ဥပမာ:\n/addcard Sakura | Epic"
        )
        return

    text = " ".join(context.args)

    if "|" not in text:
        await msg.reply_text(
            "Name နဲ့ Rarity ကြားမှာ | ထည့်ပေးပါ။"
        )
        return

    name, rarity = [x.strip() for x in text.split("|", 1)]

    if not name or rarity not in RARITIES:
        await msg.reply_text(
            "❌ Rarity မှားနေပါတယ်။\n\n" +
            "\n".join(RARITIES)
        )
        return

    photo = msg.reply_to_message.photo[-1]

    DB.execute(
        """INSERT INTO cards
        (name, file_id, file_unique_id, rarity)
        VALUES (?, ?, ?, ?)""",
        (name, photo.file_id, photo.file_unique_id, rarity)
    )
    DB.commit()

    card_id = DB.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    await msg.reply_text(
        f"✅ Card Added!\n"
        f"🎴 ID: #{card_id}\n"
        f"💎 Rarity: {rarity}\n"
        f"Name: {name}"
    )


# ========== FIND NAME ==========

async def find_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if not msg.reply_to_message:
        await msg.reply_text(
            "ကတ်ပုံကို Reply လုပ်ပြီး /w သို့မဟုတ် .w ပို့ပါ။"
        )
        return

    target = msg.reply_to_message

    card = None

    # Find by photo
    if target.photo:
        unique_id = target.photo[-1].file_unique_id
        card = DB.execute(
            "SELECT * FROM cards WHERE file_unique_id = ?",
            (unique_id,)
        ).fetchone()

    # Find by card ID in caption
    if not card and target.caption:
        match = re.search(r"CARD ID:\s*#?(\d+)", target.caption)

        if match:
            card = DB.execute(
                "SELECT * FROM cards WHERE id = ?",
                (int(match.group(1)),)
            ).fetchone()

    if card:
        await msg.reply_text(
            f"🔍 CARD FOUND!\n\n"
            f"🎴 Name: {card['name']}\n"
            f"🔢 ID: #{card['id']}\n"
            f"💎 Rarity: {card['rarity']}"
        )
    else:
        await msg.reply_text(
            "❓ ဒီကတ်ကို Database ထဲမှာ မတွေ့သေးပါဘူး။"
        )


async def dot_w(update, context):
    await find_card(update, context)


# ========== CATCH ==========

async def catch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user
    chat_id = update.effective_chat.id

    if not await check_channel(user.id, context):
        await msg.reply_text(
            f"🔒 အရင် Channel ဝင်ပေးပါ။\n"
            f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
        )
        return

    pending = DB.execute(
        "SELECT card_id FROM pending WHERE chat_id = ?",
        (chat_id,)
    ).fetchone()

    if not pending:
        await msg.reply_text("❌ ဖမ်းစရာကတ်မရှိသေးပါ။")
        return

    card_id = pending["card_id"]

    DB.execute(
        """INSERT INTO collections(user_id, card_id, quantity)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, card_id)
        DO UPDATE SET quantity = quantity + 1""",
        (user.id, card_id)
    )

    DB.execute(
        "DELETE FROM pending WHERE chat_id = ?",
        (chat_id,)
    )
    DB.commit()

    card = DB.execute(
        "SELECT * FROM cards WHERE id = ?",
        (card_id,)
    ).fetchone()

    await msg.reply_text(
        f"🎉 CARD CAUGHT!\n\n"
        f"👤 Player: {user.first_name}\n"
        f"🎴 Name: {card['name']}\n"
        f"🔢 ID: #{card['id']}\n"
        f"💎 Rarity: {card['rarity']}"
    )


# ========== COLLECTION ==========

async def collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    result = DB.execute("""
        SELECT cards.*, collections.quantity
        FROM collections
        JOIN cards ON cards.id = collections.card_id
        WHERE collections.user_id = ?
        ORDER BY cards.id
    """, (user_id,)).fetchall()

    if not result:
        await update.message.reply_text(
            "📦 Collection ဗလာဖြစ်နေပါတယ်။"
        )
        return

    text = "🏆 YOUR CARD COLLECTION\n\n"

    for card in result:
        text += (
            f"🎴 #{card['id']} {card['name']}\n"
            f"💎 {card['rarity']} | x{card['quantity']}\n\n"
        )

    await update.message.reply_text(text)


# ========== OWNER DROP ==========

async def owner_drop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return

    await send_drop(update.effective_chat.id, context)


# ========== GROUP AUTO DROP ==========

async def group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if not msg or not msg.text or msg.text.startswith("/"):
        return

    if msg.from_user and msg.from_user.is_bot:
        return

    chat_id = update.effective_chat.id

    # Count whitespace-separated words
    words = len(msg.text.split())

    DB.execute("""
        INSERT INTO group_counts(chat_id, word_count)
        VALUES (?, ?)
        ON CONFLICT(chat_id)
        DO UPDATE SET word_count = word_count + ?
    """, (chat_id, words, words))

    DB.commit()

    count = DB.execute(
        "SELECT word_count FROM group_counts WHERE chat_id = ?",
        (chat_id,)
    ).fetchone()["word_count"]

    while count >= 100:
        DB.execute(
            "UPDATE group_counts SET word_count = word_count - 100 WHERE chat_id = ?",
            (chat_id,)
        )
        DB.commit()

        await send_drop(chat_id, context)

        count -= 100


# ========== MAIN ==========

def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN":
        raise ValueError("BOT_TOKEN ထည့်ပေးပါ။")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addcard", addcard))
    app.add_handler(CommandHandler("w", find_card))
    app.add_handler(CommandHandler("catch", catch))
    app.add_handler(CommandHandler("collection", collection))
    app.add_handler(CommandHandler("drop", owner_drop))

    app.add_handler(
        MessageHandler(filters.Regex(r"^\.w$"), dot_w)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            group_messages
        )
    )

    print("🎴 Anime Card Bot Started!")
    app.run_polling()


if __name__ == "__main__":
    main()
  
