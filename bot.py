import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = "8763867582:AAHprPhPZHc2GfzsH2_GAemnUZkXlI3I62Q"

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👤 Create Profile", callback_data="profile")],
        [InlineKeyboardButton("🔍 Search", callback_data="search")],
        [InlineKeyboardButton("❤️ Likes", callback_data="likes")],
        [InlineKeyboardButton("❌ Pass", callback_data="pass")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "💕 Welcome to Dating Forever!\n"
        "Let's find you a match. Start by creating your profile.",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "profile":
        await query.edit_message_text("📝 Send me your name.")
    elif data == "search":
        await query.edit_message_text("🔍 Searching for matches near you... (coming soon)")
    elif data == "likes":
        await query.edit_message_text("❤️ Nobody has liked you yet. Keep searching!")
    elif data == "pass":
        await query.edit_message_text("🚫 You passed on this one.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
