```python
import os, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO)

ADMIN_ID = 6205405530
TOKEN = os.getenv("BOT_TOKEN")

users = {}
matches = []
chats = {}
pending = {}

async def start(update, ctx):
    u = update.effective_user
    if u.id not in users:
        users[u.id] = {"name": u.full_name, "username": u.username, "bio": "—"}
    kb = [[InlineKeyboardButton("💬 Find a partner", callback_data="find")]]
    await update.message.reply_text(f"Welcome, {u.first_name}! Find someone 👇",
                                    reply_markup=InlineKeyboardMarkup(kb))

async def find(update, ctx):
    q = update.callback_query
    uid = q.from_user.id
    for other_id, prof in users.items():
        if other_id == uid:
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
    if u.id not in pending:
        return await update.message.reply_text("Use /start and match first 👆")
    partner = pending[u.id]
    key = f"{min(u.id, partner)}-{max(u.id, partner)}"
    chats.setdefault(key, []).append({"from": u.id, "text": update.message.text})
    await context.bot.send_message(partner, f"💬 {update.message.text}")
    await update.message.reply_text("✅ Sent")

---------- ADMIN ----------
async def stats(update, context):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("Admin only ❌")
    await update.message.reply_text(
        f"📊 Stats\nUsers: {len(users)}\nMatches: {len(matches)}\n"
        f"Messages: {sum(len(v) for v in chats.values())}")

async def all_users(update, context):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("Admin only ❌")
    lines = [f"{uid} | {p['name']} | @{p['username']}" for uid, p in users.items()]
    await update.message.reply_text(f"Subscribers ({len(users)}):\n" +
                                    ("\n".join(lines) or "None"))

async def history(update, context):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("Admin only ❌")
    try:
        target = int(context.args[0])
    except (IndexError, ValueError):
    return await update.message.reply_text("Usage: /history <user_id>")
    out = []
    for key, msgs in chats.items():
        if str(target) in key:
            for m in msgs:
                out.append(f"{'Me' if m['from'] == target else 'Other'}: {m['text']}")
    await update.message.reply_text(f"Chat of {target}:\n" +
                                    ("\n".join(out[-30:]) or "No messages"))

async def full_view(update, context):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("Admin only ❌")
    try:
        target = int(context.args[0])
    except (IndexError, ValueError):
        return await update.message.reply_text("Usage: /view <user_id>")
    p = users.get(target, {})
    await update.message.reply_text(f"👤 {target}\nName: {p.get('name')}\n"
                                    f"Username: @{p.get('username')}\nBio: {p.get('bio')}")

async def block(update, context):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("Admin only ❌")
    await update.message.reply_text("⛔ Blocking user (coming in next version)")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("users", all_users))
app.add_handler(CommandHandler("history", history))
app.add_handler(CommandHandler("view", full_view))
app.add_handler(CommandHandler("block", block))
app.add_handler(CallbackQueryHandler(find, pattern="^find$"))
app.add_handler(CallbackQueryHandler(chat_start, pattern="^msg_"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_msg))

app.run_polling()
```
