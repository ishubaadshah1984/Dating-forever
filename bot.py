import logging
import asyncio
import os
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          MessageHandler, filters)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6205405530"))

users = {}
matches = {}
pending = []
banned = set()

URL_PATTERN = re.compile(r'https?://\S+|www\.\S+')

def anon_name(uid):
    return f"User_{str(uid)[-4:]}"

def is_admin(uid):
    return uid == ADMIN_ID

def reg_user(u):
    users.setdefault(u.id, {
        "name": u.first_name or "User",
        "anon": anon_name(u.id),
        "age": None, "city": None, "bio": None
    })

def profile_text(uid):
    p = users[uid]
    info = f"{p['anon']}"
    if p['age']:
        info += f" · {p['age']}"
    if p['city']:
        info += f" · {p['city']}"
    if p['bio']:
        info += f"\n💬 \"{p['bio']}\""
    return info

async def try_match(context):
    global pending
    while len(pending) >= 2:
        a = pending.pop(0)
        b = pending.pop(0)
        if a in banned or b in banned:
            continue
        matches[a] = {"other_anon": users[b]["anon"], "other_info": profile_text(b)}
        matches[b] = {"other_anon": users[a]["anon"], "other_info": profile_text(a)}
        kb = [[InlineKeyboardButton("✍️ Say hi", callback_data=f"msg_{b}")]]
        await context.bot.send_message(a, f"🎉 Matched with {users[b]['anon']}!\n{profile_text(b)}",
                                       reply_markup=InlineKeyboardMarkup(kb))
        kb2 = [[InlineKeyboardButton("✍️ Say hi", callback_data=f"msg_{a}")]]
        await context.bot.send_message(b, f"🎉 Matched with {users[a]['anon']}!\n{profile_text(a)}",
                                       reply_markup=InlineKeyboardMarkup(kb2))

async def start_cmd(update, context):
    u = update.effective_user
    reg_user(u)
    kb = [[InlineKeyboardButton("🔍 Find partner", callback_data="find")]]
    if is_admin(u.id):
        kb.append([InlineKeyboardButton("🛡️ Admin panel", callback_data="admin_panel")])
    await update.message.reply_text(
        f"Hi {u.first_name}! Set your profile:\nSend: `age city`\nExample: `24 Berlin`\nThen tap find 👇",
        reply_markup=InlineKeyboardMarkup(kb))

async def set_profile(update, context):
    u = update.effective_user
    reg_user(u)
    parts = update.message.text.split()
    if len(parts) >= 1 and parts[0].isdigit() and len(parts) <= 3:
        users[u.id]["age"] = parts[0]
        if len(parts) > 1:
            users[u.id]["city"] = " ".join(parts[1:])
        await update.message.reply_text(f"✅ Profile: {profile_text(u.id)}")
    else:
        users[u.id]["bio"] = update.message.text
        await update.message.reply_text("✅ Bio saved!")

async def find_cb(update, context):
    q = update.callback_query
    uid = q.from_user.id
    if uid in banned:
        return await q.answer("🚫 Banned")
    reg_user(q.from_user)
    if not users[uid].get("age"):
        return await q.answer("Set age/city first!", show_alert=True)
    pending.append(uid)
    await q.answer("Searching…")
    await try_match(context)
async def update_msg(update, context):
    uid = update.effective_user.id
    if uid in banned:
        return await update.message.reply_text("🚫 Banned.")
    if URL_PATTERN.search(update.message.text):
        return await update.message.reply_text("Links not allowed 🔒")
    if not users[uid].get("age") and update.message.text.split()[0].isdigit():
        return await set_profile(update, context)
    if uid in matches:
        partner = matches[uid].get("other")
        if isinstance(partner, int):
            await context.bot.send_message(partner, f"💬 {update.message.text}")
        else:
            await update.message.reply_text("Choose a match via ✍️ first")
    else:
        await update.message.reply_text("No active chat — tap 🔍 Find partner")

async def reply_cb(update, context):
    q = update.callback_query
    src = q.from_user.id
    target = int(q.data.split("_")[1])
    if target not in matches and src not in matches:
        return await q.answer("Session ended", show_alert=True)
    matches[src] = {"other": target, "other_anon": users[target]["anon"],
                    "other_info": profile_text(target)}
    await q.answer("Connected!")
    await q.message.reply_text("🔗 Chat open! Send messages freely.")

async def ban_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("⛔ Admins only")
    try:
        tid = int(context.args[0].lstrip("@"))
    except Exception:
        return await update.message.reply_text("Usage: /ban <id>")
    banned.add(tid)
    await update.message.reply_text(f"✅ Banned {tid}")

async def unban_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("⛔ Admins only")
    tid = int(context.args[0])
    banned.discard(tid)
    await update.message.reply_text(f"✅ Unbanned {tid}")

async def admin_panel_cb(update, context):
    q = update.callback_query
    if not is_admin(q.from_user.id):
        return await q.answer("⛔ Admins only")
    await q.message.reply_text(
        f"🛡️ Admin\nActive: {len(users)} users · {len(pending)} searching\n"
        f"Commands:\n/ban <id>  /unban <id>")

async def  main_cb(update, context):
    q = update.callback_query
    if q.data == "find":
        return await find_cb(update, context)
    if q.data == "admin_panel":
        return await admin_panel_cb(update, context)
    return await reply_cb(update, context)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CallbackQueryHandler(main_cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, update_msg))
    import asyncio

async def main():
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
