import os
import json
import logging
import asyncio
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

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
    ADMIN_IDS = []

# --- FIREBASE SETUP ---
if not firebase_admin._apps:
    if SERVICE_ACCOUNT_JSON:
        try:
            cred_dict = json.loads(SERVICE_ACCOUNT_JSON)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            print(f"Firebase Init Error: {e}")
    else:
        if os.path.exists("serviceAccountKey.json"):
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)

db = firestore.client()
users_ref = db.collection("users")
settings_ref = db.collection("bot_settings").document("config")
stats_ref = db.collection("bot_stats").document("general")

executor = ThreadPoolExecutor(max_workers=20)

GLOBAL_CONFIG = {
    "video_link": "https://t.me/skyzoneit/6300",
    "admin_username": "@SKYZONE_IT_ADMIN"
}

async def async_firestore_get(doc_ref):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, doc_ref.get)

async def async_firestore_set(doc_ref, data, merge=True):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, lambda: doc_ref.set(data, merge=merge))

# --- FLASK SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Skyzone IT Bot High-Performance Mode is ON!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    try:
        app.run(host='0.0.0.0', port=port, use_reloader=False)
    except:
        pass

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- STATIC CONTENT ---
STATIC_CONFIG = {
    "terms_text": """ ⚠️ **আপনাকে এই শর্তগুলো দেওয়া হলো** ⚠️
... (শর্তাবলী পূর্বের ন্যায়) ...
""",
    "final_phrase": "ইনশাআল্লাহ আমি পারবো",
    "form_link": "https://forms.gle/TYdZFiFEJcrDcD2r5",
}

QUESTIONS = [
    {"id": 1, "q": "1️⃣ আপনি কি ভিডিওটি সম্পূর্ণ মনোযোগ দিয়ে দেখেছেন?", "a": ["hea", "ji", "yes", "ha", "সম্পূর্ণ ভিডিও দেখছি", "দেখছি", "জি", "ho", "dekhsi"], "threshold": 70},
    {"id": 2, "q": "2️⃣ ভিডিও দেখে আপনি কী বুঝেছেন?", "a": ["Kivabe app use Korte hobe", "ভিডিওটি দেখে বুঝতে পারছি আমি যেভাবে এখানে আইসি সেভাবেই অন্যদেরকে নিয়ে আসতে হবে", "পরবর্তী", "ভিডিও দেখে সকল কিছু শিখতে পারলাম", "Facebook e post kore user k telegram e aina", "review apnder app e submit dite hobe", "marketing korbo", "apps review"], "threshold": 50},
    {"id": 3, "q": "3️⃣ আপনি কোন ফোন থেকে রিভিউ দেবেন? (নিজের/পরিবারের ফোন ও একই লোকেশন নিষিদ্ধ)", "a": ["ami nijer phn theke review dibo na", "অন্যদের ফোন থেকে", "মার্কেটিং করে অন্যদের ফোন থেকে রিভিউ দেওয়াতে হবে", "review amr worker dibe", "worker er phone", "onno manush diye", "user er phone"], "threshold": 60},
    {"id": 4, "q": "4️⃣ আপনি মোট কয়টি রিভিউ দিতে পারবেন?", "a": ["joto golo limit thakbe", "5 tar moto", "অ্যাপে যে লিমিট দেওয়া থাকবে ওই অনুযায়ী দিতে পারব", "অ্যাপের নির্দেশনা অনুযায়ী দিতে পারব", "unlimited", "jotogula lagbe"], "threshold": 50},
    {"id": 5, "q": "5️⃣ আপনার কি আগে থেকে কোনো অভিজ্ঞতা আছে, নাকি একদম নতুন?", "a": ["noton", "new", "অভিজ্ঞতা আছে", "আমি একদম নতুন", "নতুন", "অভিজ্ঞতা আছে", "experience nai", "agerr oviggota ace"], "threshold": 60},
    {"id": 6, "q": "6️⃣ আপনি দিনে কোন সময়ে কাজ করতে স্বাচ্ছন্দ্যবোধ করবেন?", "a": ["user jeita bolbe", "নির্দিষ্ট সময় নাই", "অ্যাপে যে সময় দেওয়া থাকবে ওই সময় থেকে", "আপনারা যে সময় দিবেন ওই সময় থেকে", "jekono somoy", "shokal", "bikal", "rat", "all time"], "threshold": 40},
    {"id": 7, "q": "7️⃣ আপনি কি এই কাজগুলোর দায়িত্ব নিয়ে নিয়মিত করতে পারবেন?", "a": ["hea", "ji", "yes", "ইনশাআল্লাহ পারবো", "চেষ্টা করব", "ইনশাআল্লাহ", "অবশ্যই", "জি", "parbo"], "threshold": 80},
    {"id": 8, "q": "8️⃣ আমাদের সব নিয়ম ও শর্ত মেনে কাজ করতে পারবেন তো?", "a": ["hea", "ji", "yes", "parbo", "ইনশাআল্লাহ", "সব শর্ত মানব", "চেষ্টা করব", "ইনশাআল্লাহ চেষ্টা করব", "InshaAllah"], "threshold": 80},
    {"id": 9, "q": "9️⃣ ভিডিওতে বলা হয়েছে — সর্বনিম্ন কত টাকা হলে উত্তোলন করা যাবে?", "a": ["50", "panchas", "৫০", "৫০ টাকা", "সর্বনিম্ন ৫০ টাকা", "ponchash"], "threshold": 90},
    {"id": 10, "q": "🔟 আপনি কীভাবে মার্কেটিং করতে চান? (সংক্ষেপে)", "a": ["Facebook e post kore", "ফেসবুক মার্কেটিং করে", "ফেসবুক মার্কেটিং করে বিভিন্ন গ্রুপে পোস্ট করে", "ফেসবুক গ্রুপে পোস্ট করে", "userder sathe contect kore", "social media", "marketing kore"], "threshold": 50}
]

async def load_config_to_cache():
    global GLOBAL_CONFIG
    try:
        doc = await async_firestore_get(settings_ref)
        if doc.exists:
            data = doc.to_dict()
            GLOBAL_CONFIG.update(data)
            logger.info("Config loaded to RAM")
        else:
            await async_firestore_set(settings_ref, GLOBAL_CONFIG)
    except Exception as e:
        logger.error(f"Config Load Error: {e}")

async def update_config_cache(key, value):
    global GLOBAL_CONFIG
    GLOBAL_CONFIG[key] = value
    await async_firestore_set(settings_ref, {key: value}, merge=True)

async def increment_stat(field):
    try:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(executor, lambda: stats_ref.set({field: firestore.Increment(1)}, merge=True))
    except:
        pass

async def get_stats_safe():
    try:
        doc = await async_firestore_get(stats_ref)
        if doc.exists:
            return doc.to_dict()
    except:
        pass
    return {}

async def get_user_data(user_id):
    try:
        doc = await async_firestore_get(users_ref.document(str(user_id)))
        if doc.exists:
            return doc.to_dict()
    except:
        pass
    return {"state": "IDLE", "q_index": 0, "answers": [], "passed": False}

async def update_user_data(user_id, data):
    await async_firestore_set(users_ref.document(str(user_id)), data)

async def delete_user_data(user_id):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(executor, lambda: users_ref.document(str(user_id)).delete())

def get_main_menu_kb():
    keyboard = [
        [InlineKeyboardButton("🚀 ইন্টারভিউ শুরু করুন", callback_data="start_exam")],
        [InlineKeyboardButton("🔄 আমার তথ্য রিসেট", callback_data="reset_me")],
        [InlineKeyboardButton("📢 সাপোর্ট গ্রুপ", url=f"https://t.me/{GROUP_CHAT_ID.replace('-100','')}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_menu_kb():
    keyboard = [
        [InlineKeyboardButton("📊 পরিসংখ্যান (Stats)", callback_data="admin_stats")],
        [InlineKeyboardButton("🎥 ভিডিও লিংক পরিবর্তন", callback_data="admin_set_video")],
        [InlineKeyboardButton("👤 অ্যাডমিন ইউজারনেম সেট", callback_data="admin_set_username")],
        [InlineKeyboardButton("❌ প্যানেল বন্ধ করুন", callback_data="admin_close")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        chat_type = update.effective_chat.type
        if chat_type == 'private':
            if user.id in ADMIN_IDS:
                try:
                    await update.message.reply_text(
                        f"⚙️ **Admin Control Panel**\nস্বাগতম {user.first_name}!",
                        reply_markup=get_admin_menu_kb(),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except: pass
            video_link = GLOBAL_CONFIG.get("video_link", "https://t.me/skyzoneit/6300")
            await update.message.reply_text(
                f"হ্যালো {user.first_name}! 👋\n\nSkyzone IT-তে স্বাগতম। কাজ শুরু করার জন্য আগে ভিডিওটি দেখুন:\n🎥 {video_link}\n\nভিডিও দেখা শেষ হলে নিচের বাটনে ক্লিক করে ইন্টারভিউ শুরু করুন।",
                reply_markup=get_main_menu_kb(),
                disable_web_page_preview=False
            )
    except Exception as e:
        logger.error(f"Start Error: {e}")
        await update.message.reply_text("হ্যালো! বট চালু আছে। নিচে ক্লিক করুন:", reply_markup=get_main_menu_kb())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    try: await query.answer()
    except: pass

    if data.startswith("admin_") and user_id in ADMIN_IDS:
        if data == "admin_stats":
            stats = await get_stats_safe()
            msg = f"📊 **Live Stats**\n\n✅ Passed Users: {stats.get('passed_users', 0)}\n📝 Interviews Started: {stats.get('total_interviews', 0)}\n📅 Time: {datetime.now().strftime('%H:%M')}"
            await query.edit_message_text(msg, reply_markup=get_admin_menu_kb(), parse_mode=ParseMode.MARKDOWN)
            return
        elif data == "admin_set_video":
            context.user_data['admin_state'] = 'WAITING_VIDEO_LINK'
            await query.edit_message_text("🎥 নতুন ভিডিও লিংকটি ইনবক্সে সেন্ড করুন:")
            return
        elif data == "admin_set_username":
            context.user_data['admin_state'] = 'WAITING_ADMIN_USER'
            await query.edit_message_text("👤 স্লিপে দেখানোর জন্য অ্যাডমিন ইউজারনেম সেন্ড করুন (Example: @MyUser):")
            return
        elif data == "admin_close":
            await query.delete_message()
            return

    user_data = await get_user_data(user_id)
    if data == "start_exam":
        if user_data.get("passed"):
            await query.edit_message_text("✅ আপনি ইতিমধ্যে ইন্টারভিউ পাস করেছেন। আপনার স্লিপ পেতে 'Slip' লিখুন।")
            return
        if user_data.get("state") == "IDLE":
             asyncio.create_task(increment_stat("total_interviews"))
        user_data["state"] = "READY_CHECK"
        await update_user_data(user_id, user_data)
        keyboard = [[InlineKeyboardButton("✅ আমি প্রস্তুত", callback_data="confirm_ready")]]
        await query.edit_message_text("আপনি কি ১০টি প্রশ্নের উত্তর দিতে প্রস্তুত?", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "confirm_ready":
        user_data["state"] = "INTERVIEW"
        user_data["q_index"] = 0
        user_data["answers"] = []
        await update_user_data(user_id, user_data)
        await query.edit_message_text(f"চমৎকার! ১ম প্রশ্ন:\n\n{QUESTIONS[0]['q']}")
    elif data == "accept_terms":
        user_data["state"] = "WAITING_PHRASE"
        await update_user_data(user_id, user_data)
        await query.edit_message_text(f"শর্তগুলো মানলে নিচের বাক্যটি লিখে মেসেজ দিন:\n\n`{STATIC_CONFIG['final_phrase']}`", parse_mode=ParseMode.MARKDOWN)
    elif data == "reset_me":
        await delete_user_data(user_id)
        await query.edit_message_text("🔄 আপনার সকল তথ্য রিসেট করা হয়েছে। আপনি চাইলে আবার শুরু করতে পারেন।", reply_markup=get_main_menu_kb())

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_message.text:
        return
    if update.effective_chat.type != 'private':
        try:
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            member = await context.bot.get_chat_member(chat_id, user_id)
            if member.status in ['creator', 'administrator']:
                return
        except Exception: pass

        msg = update.effective_message.text.strip().lower()
        user = update.effective_user
        my_link = GLOBAL_CONFIG.get("video_link", "https://t.me/skyzoneit/6300")
        
        keywords = [
            "it", "হ্যালো", "hello", "hi", "হাই", "কি কাজ", "কাজ কি", "কাজ কী", 
            "kaj ki", "ki kaj", "আমি কাজ করতে চাই", "ami kaj korte chai", 
            "কাজ চাই", "আমি নতুন", "ami notun", "i am new", "ami new", 
            "কিভাবে কাজ করব", "help me", "income", "কাজ শিখব", "kaj ache", "work"
        ]
        
        if any(key in msg for key in keywords):
            response_text = (
                f"আসসালামু আলাইকুম {user.mention_html()}!\n\n"
                f"আপনি যদি আমাদের সাথে <b>কাজ করতে চান</b>, তবে নিচের নিয়মটি ফলো করুন:\n\n"
                f"✅ প্রথমে <a href='{my_link}'>এখানে ক্লিক করে ইনবক্সে আসুন</a>।\n"
                f"✅ ইনবক্সে এসে সরাসরি <b>'IT'</b> লিখে মেসেজ দিন।\n"
                f"✅ তারপর কাজের ভিডিও এবং বিস্তারিত তথ্য অটোমেটিক পেয়ে যাবেন।\n\n"
                f"<i>অনুগ্রহ করে উপরের তথ্যগুলো ভালো করে পড়ে লিংকে ক্লিক করুন।</i>"
            )
            try:
                await update.effective_message.reply_text(response_text, parse_mode='HTML', disable_web_page_preview=True)
            except Exception as e:
                logger.error(f"Group Reply Error: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # যদি মেসেজটি গ্রুপ থেকে আসে, তবে গ্রুপ হ্যান্ডলারে পাঠাও
    if update.effective_chat.type != 'private':
        await handle_group_messages(update, context)
        return

    user = update.effective_user
    user_id = user.id
    msg = update.message.text.strip() if update.message.text else ""
    
    if user_id in ADMIN_IDS and 'admin_state' in context.user_data:
        state = context.user_data['admin_state']
        if state == 'WAITING_VIDEO_LINK':
            await update_config_cache("video_link", msg)
            del context.user_data['admin_state']
            await update.message.reply_text(f"✅ ভিডিও লিংক আপডেট করা হয়েছে।", reply_markup=get_admin_menu_kb())
            return
        elif state == 'WAITING_ADMIN_USER':
            username = msg if msg.startswith("@") else f"@{msg}"
            await update_config_cache("admin_username", username)
            del context.user_data['admin_state']
            await update.message.reply_text(f"✅ অ্যাডমিন ইউজারনেম সেট করা হয়েছে: {username}", reply_markup=get_admin_menu_kb())
            return

    if msg.upper() == "IT":
        await update.message.reply_text("নিচের মেনু থেকে ইন্টারভিউ শুরু করুন:", reply_markup=get_main_menu_kb())
        return

    user_data = await get_user_data(user_id)
    state = user_data.get("state")

    if state == "INTERVIEW":
        idx = user_data.get("q_index", 0)
        if idx >= len(QUESTIONS): idx = len(QUESTIONS) - 1
        current_q = QUESTIONS[idx]
        is_correct = False
        for ans in current_q['a']:
            if token_set_ratio(msg.lower(), ans.lower()) >= current_q['threshold']:
                is_correct = True
                break
        if is_correct:
            user_data["answers"].append({"q": current_q['q'], "a": msg})
            if idx + 1 < len(QUESTIONS):
                user_data["q_index"] = idx + 1
                await update_user_data(user_id, user_data)
                await update.message.reply_text(f"✅ সঠিক! পরবর্তী প্রশ্ন:\n\n{QUESTIONS[idx+1]['q']}")
            else:
                user_data["state"] = "TERMS"
                await update_user_data(user_id, user_data)
                kb = [[InlineKeyboardButton("🤝 আমি সকল শর্ত মেনে নিচ্ছি", callback_data="accept_terms")]]
                await update.message.reply_text(f"অভিনন্দন! সব প্রশ্নের উত্তর দিয়েছেন।\n\n{STATIC_CONFIG['terms_text']}", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("❌ উত্তরটি সঠিক হয়নি। ভিডিওটি আবার দেখে চেষ্টা করুন।")

    elif state == "WAITING_PHRASE":
        if token_set_ratio(msg.lower(), STATIC_CONFIG['final_phrase'].lower()) > 85:
            user_data["state"] = "PASSED"
            user_data["passed"] = True
            await update_user_data(user_id, user_data)
            asyncio.create_task(increment_stat("passed_users"))
            form_text = f"⚡ Official Notice ⚡\n\n✅ আপনার ইন্টারভিউ সফল হয়েছে।\n📋 এখন এই ফর্মটি পূরণ করুন: <a href='{STATIC_CONFIG['form_link']}'>Form Link</a>\n\nফর্ম পূরণ শেষে আপনার স্লিপ পেতে 'Slip' লিখুন।"
            await update.message.reply_text(form_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        else:
            await update.message.reply_text(f"ভুল হয়েছে। হুবহু এটি লিখুন: `{STATIC_CONFIG['final_phrase']}`", parse_mode=ParseMode.MARKDOWN)

    elif msg.lower() == "slip":
        if not user_data.get("passed"):
            await update.message.reply_text("আপনি এখনো ইন্টারভিউ পাশ করেননি।")
            return
        admin_user = GLOBAL_CONFIG.get("admin_username", "@SKYZONE_IT_ADMIN")
        slip = f"📄 **SKYZONE IT - RECRUITMENT SLIP**\n━━━━━━━━━━━━━━━\n👤 User: {user.first_name}\nID: <code>{user_id}</code>\n📅 Date: {datetime.now().strftime('%d/%m/%Y')}\n━━━━━━━━━━━━━━━\n"
        for item in user_data.get("answers", []):
            slip += f"• {item['a']}\n"
        slip += f"━━━━━━━━━━━━━━━\n✅ এই স্লিপটি এডমিনকে দিন: {admin_user}"
        await update.message.reply_text(slip, parse_mode=ParseMode.HTML)
        for adm in ADMIN_IDS:
            try: await context.bot.send_message(adm, f"🚀 New Candidate Passed!\n\n{slip}", parse_mode=ParseMode.HTML)
            except: pass

async def post_init(application: Application):
    await load_config_to_cache()

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app_tg = Application.builder().token(TOKEN).post_init(post_init).build()
    
    app_tg.add_handler(CommandHandler("start", start))
    app_tg.add_handler(CommandHandler("admin", start))
    app_tg.add_handler(CallbackQueryHandler(button_handler))
    
    # MessageHandler এ filters.TEXT দিয়ে ইনবক্স এবং গ্রুপ উভয়কেই প্রসেস করা হচ্ছে
    app_tg.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Skyzone IT Bot Fixed version running...")
    app_tg.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
