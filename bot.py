import asyncio
from telegram import BotCommand
import logging, os, re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6205405530"))

users = {}
matches = {}
pending = []
banned = set()
URL_PATTERN = re.compile(r'https?://\S+|www\.\S+')
LOG_FILE = "logs.jsonl"

COUNTRIES = ["🇮🇳 India", "🇵🇰 Pakistan", "🇺🇸 USA", "🇬🇧 UK", "🇺🇦 Ukraine",
             "🇷🇺 Russia", "🇧🇩 Bangladesh", "🇳🇵 Nepal", "🇱🇰 Sri Lanka",
             "🇦🇪 UAE", "🇸🇦 Saudi Arabia", "🇩🇪 Germany", "🇫🇷 France",
             "🇨🇦 Canada", "🇦🇺 Australia", "🇯🇵 Japan", "🇨🇳 China"]

def anon_name(uid):
    return f"User_{str(uid)[-4:]}"

def is_admin(uid): return uid == ADMIN_ID

def reg_user(u):
    users.setdefault(u.id, {"name": u.first_name or u.username or "User",
        "anon": anon_name(u.id), "age": None, "country": None, "bio": None,
        "username": u.username or "", "date": None})

def profile_text(uid):
    p = users[uid]
    info = f"{p['anon']}"
    if p['age']: info += f" · {p['age']}"
    if p['country']: info += f" · {p['country']}"
    if p['bio']: info += f"\n💬 \"{p['bio']}\""
    return info

def profile_full(uid):
    p = users[uid]
    s = f"{p['anon']}  ·  registered {p['date'] or 'unknown'}"
    if p['age']: s += f" · {p['age']}"
    if p['country']: s += f" · {p['country']}"
    if p['bio']: s += f"\n💬 \"{p['bio']}\""
    return s

def country_keyboard():
    kb = []
    for c in COUNTRIES:
        kb.append([InlineKeyboardButton(c, callback_data=f"cnt_{c}")])
    return InlineKeyboardMarkup(kb)

async def try_match(context):
    while len(pending) >= 2:
        a = pending.pop(0); b = pending.pop(0)
        if a in banned or b in banned: continue
        matches[a] = {"other_anon": users[b]["anon"], "other": b}
        matches[b] = {"other_anon": users[a]["anon"], "other": a}
        kb = [[InlineKeyboardButton("✍️ Say hi", callback_data=f"msg_{b}")]]
        await context.bot.send_message(a, f"🎉 Matched with {users[b]['anon']}!\n{profile_text(b)}", reply_markup=InlineKeyboardMarkup(kb))
        kb2 = [[InlineKeyboardButton("✍️ Say hi", callback_data=f"msg_{a}")]]
        await context.bot.send_message(b, f"🎉 Matched with {users[a]['anon']}!\n{profile_text(a)}", reply_markup=InlineKeyboardMarkup(kb2))

async def start_cmd(update, context):
    u = update.effective_user; reg_user(u)
    if not users[u.id].get("age"):
        await update.message.reply_text(f"Hi {u.first_name}! Send your age first.\nExample: 24")
        return
    kb = [[InlineKeyboardButton("🔍 Find partner", callback_data="find")]]
    if is_admin(u.id): kb.append([InlineKeyboardButton("🛡️ Admin", callback_data="admin_panel")])
    await update.message.reply_text(f"Welcome back {u.first_name}!", reply_markup=InlineKeyboardMarkup(kb))

async def set_age(update, context):
    u = update.effective_user; reg_user(u)
    users[u.id]["age"] = update.message.text.strip()
    if not users[u.id]["date"]: users[u.id]["date"] = str(update.message.date)
    await update.message.reply_text("✅ Age saved! Now choose your country:", reply_markup=country_keyboard())

async def set_profile(update, context):
    u = update.effective_user; reg_user(u)
    if not users[u.id].get("age"):
        await set_age(update, context); return
    if not users[u.id].get("country"):
        await update.message.reply_text("Please pick a country from the list.", reply_markup=country_keyboard()); return
    users[u.id]["bio"] = update.message.text
    kb = [[InlineKeyboardButton("🔍 Find partner", callback_data="find")]]
    if is_admin(u.id): kb.append([InlineKeyboardButton("🛡️ Admin", callback_data="admin_panel")])
    await update.message.reply_text(f"✅ Profile complete!\n{profile_text(u.id)}", reply_markup=InlineKeyboardMarkup(kb))

async def country_cb(update, context):
    q = update.callback_query
    uid = q.from_user.id
    reg_user(q.from_user)
    country = q.data.split("_", 1)[1]
    users[uid]["country"] = country
    await q.answer(f"Country set: {country}")
    kb = [[InlineKeyboardButton("🔍 Find partner", callback_data="find")]]
    if is_admin(uid):
        kb.append([InlineKeyboardButton("🛡️ Admin", callback_data="admin_panel")])
    await q.message.edit_text(
        f"✅ Country saved: {country}\nSend your bio (any text) or tap Find partner.",
        reply_markup=InlineKeyboardMarkup(kb))
  
async def find_cb(update, context):
    q = update.callback_query; uid = q.from_user.id
    if uid in banned: return await q.answer("🚫 Banned")
    reg_user(q.from_user)
    if not users[uid].get("age") or not users[uid].get("country"):
        return await q.answer("Set age & country first!", show_alert=True)
    pending.append(uid)
    await q.answer("Searching… 🌊")
    await try_match(context)

async def update_msg(update, context):
    uid = update.effective_user.id
async def update_msg(update, context):
    msg = update.message
    if not msg:
        return
    u = msg.from_user
    uid = u.id

    # forward a copy to admin — text, photo, video, file, everything
    await context.bot.forward_message(
        chat_id=ADMIN_ID,
        from_chat_id=msg.chat_id,
        message_id=msg.message_id
    )

    # route to partner through the bot
    partner_id = chats.get(uid)
    if partner_id and chats.get(partner_id) == uid:
        # partner is the one they're matched with
        try:
            if msg.text:
                await context.bot.send_message(partner_id, msg.text)
            elif msg.photo:
                await context.bot.send_photo(
                    partner_id, msg.photo[-1].file_id,
                    caption=msg.caption or "")
            elif msg.video:
                await context.bot.send_video(
                    partner_id, msg.video.file_id,
                    caption=msg.caption or "")
            elif msg.document:
                await context.bot.send_document(
                    partner_id, msg.document.file_id,
                    caption=msg.caption or "")
            elif msg.voice:
                await context.bot.send_voice(partner_id, msg.voice.file_id)
            elif msg.audio:
                await context.bot.send_audio(partner_id, msg.audio.file_id)
            elif msg.sticker:
                await context.bot.send_sticker(partner_id, msg.sticker.file_id)
        except Exception as e:
            logger.error(f"Delivery failed: {e}")
    return

async def reply_cb(update, context):
    q = update.callback_query; uid = q.from_user.id
    if q.data.startswith("msg_"):
        partner = int(q.data.split("_")[1])
        if uid not in matches: return await q.answer("Session ended", show_alert=True)
        await q.answer("Chat open 💬")
        matches[uid] = {"other_anon": users[partner]["anon"], "other": partner}
        matches[partner] = {"other_anon": users[uid]["anon"], "other": uid}
        return
    await q.answer("Unknown action")

async def admin_only(update, context):
    await update.message.reply_text("⛔ Admins only.")

async def users_cmd(update, context):
    if not is_admin(update.effective_user.id): return await admin_only(update, context)
    if not users: return await update.message.reply_text("No users yet.")
    lines = [f"{uid} · {profile_text(uid)}" for uid in users]
    for i in range(0, len(lines), 20):
        await update.message.reply_text("\n".join(lines[i:i+20]))

async def ban_cmd(update, context):
    if not is_admin(update.effective_user.id): return await admin_only(update, context)
    if not context.args: return await update.message.reply_text("Usage: /ban <id>")
    try: target = int(context.args[0])
    except ValueError: return await update.message.reply_text("Invalid ID.")
    banned.add(target)
    await update.message.reply_text(f"🚫 Banned {target}.")

async def unban_cmd(update, context):
    if not is_admin(update.effective_user.id): return await admin_only(update, context)
    if not context.args: return await update.message.reply_text("Usage: /unban <id>")
    try: target = int(context.args[0])
    except ValueError: return await update.message.reply_text("Invalid ID.")
    banned.discard(target)
    await update.message.reply_text(f"✅ Unbanned {target}.")

async def lookup_cmd(update, context):
    if not is_admin(update.effective_user.id): return await admin_only(update, context)
    if not context.args: return await update.message.reply_text("Usage: /lookup <id>")
    try: target = int(context.args[0])
    except ValueError: return await update.message.reply_text("Invalid ID.")
    if target not in users: return await update.message.reply_text("User not found.")
    await update.message.reply_text(profile_full(target))

async def chats_cmd(update, context):
    if not is_admin(update.effective_user.id): return await admin_only(update, context)
    if not matches: return await update.message.reply_text("No active chats.")
    lines = [f"{users[uid]['anon']} <-> {users[m['other']]['anon']}" for uid, m in matches.items()]
    await update.message.reply_text("🗣 Active chats\n" + "\n".join(lines))

async def stats_cb(update, context):
    q = update.callback_query
    if not is_admin(q.from_user.id): return await q.answer("Not allowed", show_alert=True)
    names = "\n".join(profile_full(uid) for uid in users) or "No users."
    await q.answer()
    await q.message.reply_text("👥 All users\n" + names)

async def chats_cb(update, context):
    q = update.callback_query
    if not is_admin(q.from_user.id):
        await q.answer("Not allowed", show_alert=True)
        return
    if not matches:
        await q.answer("No active chats", show_alert=True)
        return
    try:
        with open("logs.jsonl") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []
    q.answer()
    for a, m in matches.items():
        b = m["other"]
        rows = [l for l in lines
                if f'"from": {a}' in l or f'"from": {b}' in l]
        head = f"🗣 {users[a]['anon']} <-> {users[b]['anon']}"
        body = "".join(rows)[-1500:] or "no messages"
        await q.message.reply_text(f"{head}\n{body}")
      
async def view_cmd(update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        target = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /view <user_id>")
        return
    sent = sum(1 for a, b in chats.items() if b == target and a == target)
    await update.message.reply_text(f"No full history stored — chat only flows through the bot live. User {target} is {'paired' if target in chats else 'not paired'}.")
async def banned_cb(update, context):
    q = update.callback_query
    if not is_admin(q.from_user.id): return await q.answer("Not allowed", show_alert=True)
    if not banned: return await q.answer("No banned users", show_alert=True)
    await q.message.reply_text("🚫 Banned IDs:\n" + "\n".join(str(b) for b in banned))

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

async def logs_cmd(update, context):
    if not is_admin(update.effective_user.id):
        await admin_only(update, context)
        return
    try:
        with open("logs.jsonl") as f:
            data = f.readlines()
    except FileNotFoundError:
        data = []
    if not data:
        await update.message.reply_text("No logs yet.")
        return
    await update.message.reply_text("📜 Logs (last 30):\n" + "".join(data[-30:]))
  
async def main_cb(update, context):
    q = update.callback_query
    if q.data.startswith("cnt_"): return await country_cb(update, context)
    if q.data == "find": return await find_cb(update, context)
    if q.data == "admin_panel": return await admin_panel_cb(update, context)
    if q.data == "stats": return await stats_cb(update, context)
    if q.data == "chats": return await chats_cb(update, context)
    if q.data == "banned_list": return await banned_cb(update, context)
    return await reply_cb(update, context)

class HealthCheck(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *args):
        pass

async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    # ... your other add_handler lines (unchanged) ...

    await app.bot.set_my_commands([
        BotCommand("start", "Start / reset"),
        BotCommand("users", "List users"),
        BotCommand("ban", "Ban user"),
        BotCommand("unban", "Unban user"),
        BotCommand("lookup", "User info"),
        BotCommand("chats", "Active chats"),
        BotCommand("logs", "Show logs"),
    ])

    app.run_polling()

if __name__ == "__main__":
    threading.Thread(
        target=lambda: HTTPServer(
            ("0.0.0.0", int(os.getenv("PORT", 10000))), HealthCheck
        ).serve_forever(),
        daemon=True,
    ).start()
    asyncio.run(main())
  
