import asyncio
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 6205405530))

users = {}
matches = []
pending = {}
chats = {}
banned = set()

def is_admin(uid):
    return uid == ADMIN_ID

async def start(update, context):
    u = update.effective_user
    users[u.id] = {"name": u.first_name, "username": u.username}
    kb = [[InlineKeyboardButton("👋 Find a partner", callback_data="find")]]
    await update.message.reply_text(
        f"Hi {u.first_name}! Ready to meet someone?",
        reply_markup=InlineKeyboardMarkup(kb))

async def find(update, context):
    q = update.callback_query
    uid = q.from_user.id
    if uid in banned:
        return await q.answer("You are banned 🚫")
    for other_id, prof in users.items():
        if other_id == uid or other_id in banned:
            continue
        if any(uid in p and other_id in p for p in matches):
            continue
        matches.append([uid, other_id])
        kb = [[InlineKeyboardButton("✍️ Send message", callback_data=f"msg_{uid}_{other_id}"),
               InlineKeyboardButton("🚫 End chat", callback_data=f"end_{uid}_{other_id}")]]
        await context.bot.send_message(uid, f"🎉 Matched with {prof['name']}! Say hi 👋",
                                       reply_markup=InlineKeyboardMarkup(kb))
        await context.bot.send_message(other_id, f"🎉 Matched with {users[uid]['name']}! Say hi 👋",
                                       reply_markup=InlineKeyboardMarkup(kb))
        return await q.answer("Matched!")
    await q.answer("No one available yet 😕")

async def chat_start(update, context):
    q = update.callback_query
    parts = q.data.split("_")
    a, b = int(parts[1]), int(parts[2])
    pending[q.from_user.id] = a if q.from_user.id == b else b
    await q.answer()
    await q.message.reply_text("Now type your message — it goes to your partner. IDs hidden 🔒")

async def route_msg(update, context):
    u = update.effective_user
    if u.id in banned:
        return await update.message.reply_text("You are banned 🚫")
    if u.id not in pending:
        return await update.message.reply_text("Use /start and match first 👆")
    partner = pending[u.id]
    key = f"{min(u.id, partner)}-{max(u.id, partner)}"
    chats.setdefault(key, []).append({"from": u.id, "text": update.message.text})
    await context.bot.send_message(partner, f"💬 {update.message.text}")
    await update.message.reply_text("✅ Sent")

async def admin_only(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Admin only ❌")
        return False
    return True

async def stats(update, context):
    if not await admin_only(update, context): return
    await update.message.reply_text(
        f"📊 Stats\nUsers: {len(users)}\nMatches: {len(matches)}\n"
        f"Banned: {len(banned)}\nMessages: {sum(len(v) for v in chats.values())}")

async def all_users(update, context):
    if not await admin_only(update, context): return
    lines = [f"{uid} | {p['name']} | @{p['username']}" for uid, p in users.items()]
    await update.message.reply_text(f"Subscribers ({len(users)}):\n" +("\n".join(lines) or "None"))

async def history(update, context):
    if not await admin_only(update, context): return
    try:
        parts = update.message.text.split(" ")
        if len(parts) < 2:
            await update.message.reply_text("Usage: /history user1id-user2id")
            return
        msgs = chats.get(parts[1], [])
        if not msgs:
            await update.message.reply_text("No messages found.")
            return
        await update.message.reply_text("\n".join(f"{m['from']}: {m['text']}" for m in msgs))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def ban_user(update, context):
    if not await admin_only(update, context): return
    try:
        uid = int(context.args[0])
        banned.add(uid)
        await update.message.reply_text(f"🚫 Banned {uid}")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /ban <userid>")

async def unban_user(update, context):
    if not await admin_only(update, context): return
    try:
        uid = int(context.args[0])
        banned.discard(uid)
        await update.message.reply_text(f"✅ Unbanned {uid}")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /unban <userid>")

async def broadcast(update, context):
    if not await admin_only(update, context): return
    text = " ".join(context.args)
    if not text:
        return await update.message.reply_text("Usage: /broadcast <message>")
    ok = 0
    for uid in list(users):
        try:
            await context.bot.send_message(uid, f"📢 {text}")
            ok += 1
        except Exception:
            pass
    await update.message.reply_text(f"📢 Sent to {ok}/{len(users)} users")

async def wipe_all(update, context):
    if not await admin_only(update, context): return
    if "confirm" not in context.args:
        return await update.message.reply_text("⚠️ Confirm: /wipe confirm")
    users.clear()
    matches.clear()
    chats.clear()
    pending.clear()
    banned.clear()
    await update.message.reply_text("🗑️ All data wiped")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("all_users", all_users))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("wipe", wipe_all))
    app.add_handler(CallbackQueryHandler(find, pattern="^find$"))
    app.add_handler(CallbackQueryHandler(chat_start, pattern="^msg_|^end_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_msg))
    app.run_polling()

async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(find, pattern="^find$"))
    app.add_handler(CallbackQueryHandler(chat_start, pattern="^msg_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_msg))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
