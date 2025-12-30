import os
import json
import logging
import asyncio
import threading
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters, 
    ContextTypes
)
from rapidfuzz.fuzz import token_set_ratio

# --- CONFIGURATION ---
TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "7870088579,7259050773")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID", "-1002337825231")
SERVICE_ACCOUNT_JSON = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "")

try:
    ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip().isdigit()]
except:
    ADMIN_IDS = [7870088579, 7259050773]

# --- FIREBASE SETUP ---
if SERVICE_ACCOUNT_JSON:
    cred_dict = json.loads(SERVICE_ACCOUNT_JSON)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
else:
    # Local testing fallback
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()
users_ref = db.collection("users")

# --- FLASK SERVER (Health Check) ---
app = Flask(__name__)
@app.route('/')
def home():
    return "Skyzone IT Bot is Running with Firebase!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG DATA ---
CONFIG = {
    "video_link": "https://www.youtube.com/",
    "terms_text": """ ⚠️ **আপনাকে এই শর্তগুলো দেওয়া হলো** ⚠️ 
    
1️⃣ সঠিক অ্যাপে রিভিউ দিতে হবে।
2️⃣ একবার সাবমিট করলে দ্বিতীয়বার করবেন না।
3️⃣ নির্ধারিত সময়ে কাজ শুরু করবেন।
4️⃣ একটি ফোন ও একটি জিমেইল ব্যবহার করবেন।
5️⃣ নতুন মেম্বারদের ইনভাইট করবেন।
6️⃣ দক্ষ কাউকে গ্রুপে অ্যাড করবেন না।
7️⃣ পেমেন্ট স্ক্রিনশট গ্রুপে দিতে হবে।
8️⃣ ভদ্র আচরণ বজায় রাখবেন।
9️⃣ ২৪ ঘণ্টা পর রেফারেলদের অ্যাড করবেন।
🔟 ভিডিও দেখে সমস্যা সমাধান করবেন।

**শর্ত মেনে চললে নিচের বাটনে ক্লিক করুন।**""",
    "final_phrase": "ইনশাআল্লাহ আমি পারবো",
    "form_link": "https://forms.gle/TYdZFiFEJcrDcD2r5",
}

QUESTIONS = [
    {"id": 1, "q": "1️⃣ আপনি কি ভিডিওটি সম্পূর্ণ মনোযোগ দিয়ে দেখেছেন?", "a": ["hea", "ji", "yes", "ha", "জি", "dekhsi"], "threshold": 70},
    {"id": 2, "q": "2️⃣ ভিডিও দেখে আপনি কী বুঝেছেন?", "a": ["Kivabe app use Korte hobe", "marketing", "review", "apps review"], "threshold": 40},
    {"id": 3, "q": "3️⃣ আপনি কোন ফোন থেকে রিভিউ দেবেন?", "a": ["onno phone", "worker phone", "marketing phone", "not family", "user phone"], "threshold": 50},
    {"id": 4, "q": "4️⃣ আপনি মোট কয়টি রিভিউ দিতে পারবেন?", "a": ["limit", "unlimited", "jotogula lagbe", "as per app"], "threshold": 40},
    {"id": 5, "q": "5️⃣ আপনার কি আগে থেকে কোনো অভিজ্ঞতা আছে?", "a": ["noton", "new", "experience", "অভিজ্ঞতা আছে", "নতুন"], "threshold": 50},
    {"id": 6, "q": "6️⃣ আপনি দিনে কোন সময়ে কাজ করতে পারবেন?", "a": ["jekono somoy", "shokal", "rat", "any time", "নির্ভর করে"], "threshold": 40},
    {"id": 7, "q": "7️⃣ দায়িত্ব নিয়ে নিয়মিত করতে পারবেন?", "a": ["hea", "ji", "yes", "parbo", "ইনশাআল্লাহ"], "threshold": 70},
    {"id": 8, "q": "8️⃣ সব নিয়ম ও শর্ত মেনে চলবেন?", "a": ["hea", "ji", "yes", "parbo", "ইনশাআল্লাহ"], "threshold": 70},
    {"id": 9, "q": "9️⃣ সর্বনিম্ন কত টাকা হলে উত্তোলন করা যাবে?", "a": ["50", "৫০", "fifty", "ponchash"], "threshold": 85},
    {"id": 10, "q": "🔟 আপনি কীভাবে মার্কেটিং করতে চান?", "a": ["facebook", "social media", "group post", "ফেসবুক"], "threshold": 40}
]

# --- DATABASE HELPERS ---
def get_user_data(user_id):
    doc = users_ref.document(str(user_id)).get()
    if doc.exists:
        return doc.to_dict()
    return {"state": "IDLE", "q_index": 0, "answers": [], "passed": False}

def update_user_data(user_id, data):
    users_ref.document(str(user_id)).set(data, merge=True)

def reset_user(user_id):
    users_ref.document(str(user_id)).delete()

# --- INTERFACE HELPERS ---
def get_main_menu_kb():
    keyboard = [
        [InlineKeyboardButton("🚀 ইন্টারভিউ শুরু করুন", callback_data="start_exam")],
        [InlineKeyboardButton("🔄 আমার তথ্য রিসেট", callback_data="reset_me")],
        [InlineKeyboardButton("📢 সাপোর্ট গ্রুপ", url=f"https://t.me/{GROUP_CHAT_ID.replace('-100','')}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.effective_chat.type != 'private': return
    
    await update.message.reply_text(
        f"হ্যালো {user.first_name}! 👋\n\nSkyzone IT-তে স্বাগতম। কাজ শুরু করার জন্য আগে ভিডিওটি দেখুন এবং নিচের বাটনে ক্লিক করে ইন্টারভিউ শুরু করুন।",
        reply_markup=get_main_menu_kb()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    user_data = get_user_data(user_id)

    if data == "start_exam":
        if user_data.get("passed"):
            await query.edit_message_text("✅ আপনি ইতিমধ্যে ইন্টারভিউ পাস করেছেন। আপনার স্লিপ পেতে /slip লিখুন।")
            return
        
        user_data["state"] = "READY_CHECK"
        update_user_data(user_id, user_data)
        
        keyboard = [[InlineKeyboardButton("✅ আমি প্রস্তুত", callback_data="confirm_ready")]]
        await query.edit_message_text("আপনি কি ১০টি প্রশ্নের উত্তর দিতে প্রস্তুত?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "confirm_ready":
        user_data["state"] = "INTERVIEW"
        user_data["q_index"] = 0
        user_data["answers"] = []
        update_user_data(user_id, user_data)
        await query.edit_message_text(f"চমৎকার! ১ম প্রশ্ন:\n\n{QUESTIONS[0]['q']}")

    elif data == "accept_terms":
        user_data["state"] = "WAITING_PHRASE"
        update_user_data(user_id, user_data)
        await query.edit_message_text(f"শর্তগুলো মানলে নিচের বাক্যটি লিখে মেসেজ দিন:\n\n`{CONFIG['final_phrase']}`", parse_mode=ParseMode.MARKDOWN)

    elif data == "reset_me":
        reset_user(user_id)
        await query.edit_message_text("🔄 আপনার সকল তথ্য রিসেট করা হয়েছে। আপনি চাইলে আবার শুরু করতে পারেন।", reply_markup=get_main_menu_kb())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    msg = update.message.text.strip()
    
    if update.effective_chat.type != 'private':
        if msg.upper() == "IT":
            await update.message.reply_text(f"{user.mention_html()}, কাজের জন্য ইনবক্সে আসুন।", parse_mode=ParseMode.HTML)
        return

    user_data = get_user_data(user_id)
    state = user_data.get("state")

    if msg.upper() == "IT":
        await update.message.reply_text("নিচের মেনু থেকে ইন্টারভিউ শুরু করুন:", reply_markup=get_main_menu_kb())
        return

    if state == "INTERVIEW":
        idx = user_data["q_index"]
        current_q = QUESTIONS[idx]
        
        is_correct = False
        for ans in current_q['a']:
            if token_set_ratio(msg.lower(), ans.lower()) >= current_q['threshold']:
                is_correct = True
                break
        
        if is_correct:
            user_data["answers"].append({"q": current_q['q'], "a": msg})
            if idx + 1 < len(QUESTIONS):
                user_data["q_index"] += 1
                update_user_data(user_id, user_data)
                await update.message.reply_text(f"✅ সঠিক! পরবর্তী প্রশ্ন:\n\n{QUESTIONS[idx+1]['q']}")
            else:
                user_data["state"] = "TERMS"
                update_user_data(user_id, user_data)
                kb = [[InlineKeyboardButton("🤝 আমি সকল শর্ত মেনে নিচ্ছি", callback_data="accept_terms")]]
                await update.message.reply_text(f"অভিনন্দন! সব প্রশ্নের উত্তর দিয়েছেন।\n\n{CONFIG['terms_text']}", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("❌ উত্তরটি সঠিক হয়নি। ভিডিওটি আবার দেখে চেষ্টা করুন।")

    elif state == "WAITING_PHRASE":
        if token_set_ratio(msg.lower(), CONFIG['final_phrase'].lower()) > 85:
            user_data["state"] = "PASSED"
            user_data["passed"] = True
            update_user_data(user_id, user_data)
            
            form_text = f"⚡ Official Notice ⚡\n\n✅ আপনার ইন্টারভিউ সফল হয়েছে।\n📋 এখন এই ফর্মটি পূরণ করুন: <a href='{CONFIG['form_link']}'>Form Link</a>\n\nফর্ম পূরণ শেষে আপনার স্লিপ পেতে 'Slip' লিখুন।"
            await update.message.reply_text(form_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        else:
            await update.message.reply_text(f"ভুল হয়েছে। হুবহু এটি লিখুন: `{CONFIG['final_phrase']}`", parse_mode=ParseMode.MARKDOWN)

    elif msg.lower() == "slip" or user_data.get("passed"):
        if not user_data.get("passed"): return
        
        slip = f"📄 **SKYZONE IT - RECRUITMENT SLIP**\n"
        slip += f"━━━━━━━━━━━━━━━\n"
        slip += f"👤 User: {user.first_name}\nID: <code>{user_id}</code>\n"
        slip += f"📅 Date: {datetime.now().strftime('%d/%m/%Y')}\n"
        slip += f"━━━━━━━━━━━━━━━\n"
        for item in user_data["answers"]:
            slip += f"• {item['a']}\n"
        slip += f"━━━━━━━━━━━━━━━\nএই স্লিপটি এডমিনকে দিন।"
        
        await update.message.reply_text(slip, parse_mode=ParseMode.HTML)
        # অটো এডমিন নোটিফিকেশন
        for adm in ADMIN_IDS:
            try: await context.bot.send_message(adm, f"🚀 New Candidate Passed!\n\n{slip}", parse_mode=ParseMode.HTML)
            except: pass

# --- ADMIN COMMANDS ---
async def admin_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    if not context.args:
        await update.message.reply_text("ইউজার আইডি দিন। উদাহরণ: `/reset 12345678`")
        return
    target_id = context.args[0]
    reset_user(target_id)
    await update.message.reply_text(f"✅ ইউজার {target_id} এর ডাটা রিসেট করা হয়েছে।")

# --- MAIN ---
def main():
    threading.Thread(target=run_flask, daemon=True).start()
    
    app_tg = Application.builder().token(TOKEN).build()
    
    app_tg.add_handler(CommandHandler("start", start))
    app_tg.add_handler(CommandHandler("reset", admin_reset))
    app_tg.add_handler(CallbackQueryHandler(button_handler))
    app_tg.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Skyzone IT Bot is running with Firebase & Buttons...")
    app_tg.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
