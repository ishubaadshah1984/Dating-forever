
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)

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
    await update.message.reply_text(f"Subscribers ({len(users)}):\n" +
