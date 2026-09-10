import logging, os, re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                         MessageHandler, filters)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "620540494"))

users = {}
matches = {}
pending = []
banned = set()
URL_PATTERN = re.compile(r'https?://\S+|www\.\S+')
ADMIN_USERNAME = "ishubaadshah1984"

def anon_name(uid): return f"User_{str(uid)[-4:]}"

def is_admin(uid): return uid == ADMIN_ID

def reg_user(u):
    users.setdefault(u.id, {"name": u.first_name or u.username or "User",
        "anon": anon_name(u.id), "age": None, "city": None, "bio": None,
        "username": u.username or "", "date": None})

def profile_text(uid):
    p = users[uid]
    info = f"{p['anon']}"
    if p['age']: info += f" · {p['age']}"
    if p['city']: info += f" · {p['city']}"
    if p['bio']: info += f"\n💬 \"{p['bio']}\""
    return info

def profile_full(uid):
    p = users[uid]
    s = f"{p['anon']}  ·  registered {p['date'] or 'unknown'}"
    if p['age']: s += f" · {p['age']}"
    if p['city']: s += f" · {p['city']}"
    if p['bio']: s += f"\n💬 \"{p['bio']}\""
    return s

async def try_match(context):
    global pending
    while len(pending) >= 2:
        a = pending.pop(0); b = pending.pop(0)
        if a in banned or b in banned: continue
        matches[a] = {"other_anon": users[b]["anon"], "other_info": profile_text(b), "other": b}
        matches[b] = {"other_anon": users[a]["anon"], "other_info": profile_text(a), "other": a}
        kb = [[InlineKeyboardButton("✍️ Say hi", callback_data=f"msg_{b}")]]
        await context.bot.send_message(a, f"🎉 Matched with {users[b]['anon']}!\n{profile_text(b)}", reply_markup=InlineKeyboardMarkup(kb))
        kb2 = [[InlineKeyboardButton("✍️ Say hi", callback_data=f"msg_{a}")]]
        await context.bot.send_message(b, f"🎉 Matched with {users[a]['anon']}!\n{profile_text(a)}", reply_markup=InlineKeyboardMarkup(kb2))

async def start_cmd(update, context):
    u = update.effective_user; reg_user(u)
    kb = [[InlineKeyboardButton("🔍 Find partner", callback_data="find")]]
    if is_admin(u.id): kb.append([InlineKeyboardButton("🛡️ Admin", callback_data="admin_panel")])
    await update.message.reply_text(f"Hi {u.first_name}! Send:  age city\nExample: 24 Berlin", reply_markup=InlineKeyboardMarkup(kb))

async def set_profile(update, context):
    u = update.effective_user; reg_user(u)
    parts = update.message.text.split()
    if len(parts) >= 1 and parts[0].isdigit() and len(parts) <= 3:
        users[u.id]["age"] = parts[0]
        if len(parts) > 1: users[u.id]["city"] = " ".join(parts[1:])
        if not users[u.id]["date"]: users[u.id]["date"] = str(update.message.date)
        await update.message.reply_text(f"✅ Profile: {profile_text(u.id)}")
    else:
        users[u.id]["bio"] = update.message.text
        await update.message.reply_text("✅ Bio saved!")

async def find_cb(update, context):
    q = update.callback_query; uid = q.from_user.id
    if uid in banned: return await q.answer("🚫 Banned")
    reg_user(q.from_user)
    if not users[uid].get("age"): return await q.answer("Set age/city first!", show_alert=True)
    pending.append(uid); await q.answer("Searching… 🌊"); await try_match(context)

async def update_msg(update, context):
    uid = update.effective_user.id
    if uid in banned:
        return await update.message.reply_text("🚫 You are banned.")
    if URL_PATTERN.search(update.message.text):
        return await update.message.reply_text("Links not allowed 🔒")
    parts = update.message.text.split()
    if not users[uid].get("age") and parts and parts[0].isdigit():
        return await set_profile(update, context)
    if uid in matches and matches[uid].get("other"):
        await context.bot.send_message(matches[uid]["other"], f"💬 {update.message.text}")
    else:
        await update.message.reply_text("No active chat — tap 🔍 Find partner")
async def reply_cb(update, context):
    q = update.callback_query; uid = q.from_user.id
    partner = int(q.data.split("_")[1])
    if uid not in matches: return await q.answer("Session ended", show_alert=True)
    await q.answer("Chat open 💬")

async def admin_only(update):
    await update.message.reply_text("⛔ Admins only.")

async def users_cmd(update, context):
    if not is_admin(update.effective_user.id): return await admin_only(update)
    if not users: return await update.message.reply_text("No users yet.")
    lines = [f"{uid} · {profile_text(uid)}" for uid in users]
    for i in range(0, len(lines), 20):
        await update.message.reply_text("\n".join(lines[i:i+20]))

async def ban_cmd(update, context):
    if not is_admin(update.effective_user.id): return await admin_only(update)
    if not context.args: return await update.message.reply_text("Usage: /ban <id>")
    try: target = int(context.args[0])
    except ValueError: return await update.message.reply_text("Invalid ID.")
    banned.add(target)
    await update.message.reply_text(f"🚫 Banned {target}.")

async def unban_cmd(update, context):
    if not is_admin(update.effective_user.id): return await admin_only(update)
    if not context.args: return await update.message.reply_text("Usage: /unban <id>")
    try: target = int(context.args[0])
    except ValueError: return await update.message.reply_text("Invalid ID.")
    banned.discard(target)
    await update.message.reply_text(f"✅ Unbanned {target}.")

async def lookup_cmd(update, context):
    if not is_admin(update.effective_user.id): return await admin_only(update)
    if not context.args: return await update.message.reply_text("Usage: /lookup <id>")
    try: target = int(context.args[0])
    except ValueError: return await update.message.reply_text("Invalid ID.")
    if target not in users: return await update.message.reply_text("User not found.")
    await update.message.reply_text(profile_full(target))

async def chats_cmd(update, context):
    if not is_admin(update.effective_user.id): return await admin_only(update)
    if not matches: return await update.message.reply_text("No active chats.")
    lines = []
    for uid, m in matches.items():
        lines.append(f"{users[uid]['anon']} <-> {m['other_anon']}")
    await update.message.reply_text("🗣 Active chats\n" + "\n".join(lines))

async def stats_cb(update, context):
    q = update.callback_query
    if not is_admin(q.from_user.id): return await q.answer("Not allowed", show_alert=True)
    names = "\n".join(profile_full(uid) for uid in users) or "No users."
    await q.answer()
    await q.message.reply_text("👥 All users\n" + names)

async def chats_cb(update, context):
    q = update.callback_query
    if not is_admin(q.from_user.id): return await q.answer("Not allowed", show_alert=True)
    if not matches: return await q.answer("No active chats", show_alert=True)
    lines = [f"{users[uid]['anon']} <-> {m['other_anon']}" for uid, m in matches.items()]
    await q.message.reply_text("🗣 Active chats\n" + "\n".join(lines))
async def banned_cb(update, context):
    q = update.callback_query
    if not is_admin(q.from_user.id): return await q.answer("Not allowed", show_alert=True)
    if not banned: return await q.answer("No banned users", show_alert=True)
    await q.message.reply_text("🚫 Banned IDs:\n" + "\n".join(f"{b}" for b in banned))

async def admin_panel_cb(update, context):
    q = update.callback_query
    if not is_admin(q.from_user.id): return await q.answer("Not allowed", show_alert=True)
    txt = (f"🛡️ Admin panel\n"
           f"👥 Users: {len(users)} · 💬 Chats: {len(matches)} · 🚫 Banned: {len(banned)}\n\n"
           f"/ban &lt;id&gt; · /unban &lt;id&gt; · /lookup &lt;id&gt; · /chats · /users")
    kb = [[InlineKeyboardButton("👥 Users", callback_data="stats"),
           InlineKeyboardButton("🗣 Chats", callback_data="chats"),
           InlineKeyboardButton("🚫 Banned", callback_data="banned_list")]]
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

async def main_cb(update, context):
    q = update.callback_query
    if q.data == "find": return await find_cb(update, context)
    if q.data == "admin_panel": return await admin_panel_cb(update, context)
    if q.data == "stats": return await stats_cb(update, context)
    if q.data == "chats": return await chats_cb(update, context)
    if q.data == "banned_list": return await banned_cb(update, context)
    return await reply_cb(update, context)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("lookup", lookup_cmd))
    app.add_handler(CommandHandler("chats", chats_cmd))
    app.add_handler(CallbackQueryHandler(main_cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, update_msg))
    app.run_polling()

if __name__ == "__main__":
    main()
