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

# অ্যাডমিন আইডি হ্যান্ডলিং
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

# --- PERFORMANCE TUNING ---
# থ্রেড সংখ্যা বাড়ানো হলো যাতে অনেক ইউজার একসাথে হ্যান্ডেল করা যায়
executor = ThreadPoolExecutor(max_workers=20)

# --- GLOBAL CACHE (SPEED BOOST) ---
# ডাটাবেস বার বার কল না করার জন্য ক্যাশ মেমোরি
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

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- STATIC CONTENT ---
STATIC_CONFIG = {
    "terms_text": """ ⚠️ **আপনাকে এই শর্তগুলো দেওয়া হলো** ⚠️
    1️⃣ সাবধান: যে অ্যাপের জন্য টেক্সট তৈরি করা হবে, সেই অ্যাপেই রিভিউ দিতে হবে। ওই টেক্সট দিয়ে অন্য কোনো অ্যাপে রিভিউ দেওয়া যাবে না।

2️⃣ একবার সাবমিট: আপনি যে অ্যাপে কাজ সাবমিট করবেন, একবার করে ফেললে দ্বিতীয়বার আর সেই কাজ সাবমিট করবেন না।

3️⃣ সময় মেনে চলা: অ্যাপস যে সময় দেওয়া থাকবে, সেই সময় থেকেই কাজ শুরু করবেন।

4️⃣ একটি ফোন, একটি জিমেইল: আপনি যে অ্যাপে একবার রিভিউ দিবেন, একটি ফোন ও একটি জিমেইল দিয়ে। ওই অ্যাপে যে ফোন দিয়ে রিভিউ দিয়েছেন, সেই ফোন দিয়ে আর রিভিউ দেওয়া যাবে না। ওই অ্যাপে

5️⃣ নতুন মানুষ আনা: মনে রাখবেন, আপনি যেভাবে এখানে এসেছেন, ঠিক সেইভাবেই অন্যদেরও নিয়ে আসবেন।

6️⃣ সঠিক গ্রুপ এড: আপনার থেকে বেশি বোঝে এমন কাউকে গ্রুপে এড করবেন না।

7️⃣ পেমেন্ট স্ক্রিনশট: পেমেন্ট পাওয়ার পর পেমেন্টের স্ক্রিনশট গ্রুপে পোস্ট করতে হবে।

8️⃣ ভদ্র আচরণ: সবার সাথে ভালো ব্যবহার করবেন এবং যাদের নিয়ে আসবেন, তাদের সাথেও ভদ্র আচরণ করবেন।

9️⃣ ২৪ ঘণ্টা নিয়ম: আপনি যাদের দিয়ে রিভিউ করাবেন, তাদেরকে ২৪ ঘণ্টা পর গ্রুপে এড করতে হবে।

🔟 সমস্যা সমাধান: কোনো সমস্যা হলে ভিডিও দেখে সমাধান করবেন।
সতর্কবার্তা:
❌ আপনার নেটওয়ার্কের ভেতরে যেগুলো ডিভাইস থাকবে সেগুলো থেকে রিভিউ দিতে পারবেন না
❌ নির্ধারিত সময়ের আগে মার্কেটিং করা
❌ আগে থেকেই ওয়ার্কার ঠিক করে রাখা
❌ সাবমিট অপশন চালু হতেই সঙ্গে সঙ্গে সাবমিট করে ফেলা
❌একই লোকেশন থেকে একাধিক রিভিউ দেওয়া যাবে না, ফ্যামিলি এবং নিজের ফোন থেকে রিভিউ দেওয়া যাবে না❌

ফলাফল:
🚫 আপনার অ্যাকাউন্ট ব্যান হবে 
🚫 ব্যালেন্স ফ্রিজ করা হবে 
🚫 আর কখনো কাজ করতে পারবেন না
👉 তাই সাবধান থাকবেন।
অ্যাপসে যে সময় দেওয়া থাকবে, সেই সময় থেকে মার্কেটিং শুরু করবেন।
তারপর কোনো ওয়ার্কার যদি নক করে, তখনই কাজ শুরু ও সাবমিট করবেন।
শুধু যে কাজ দেওয়া হবে সেটাই সাবমিট করতে হবে।
⚠️ আগেভাগে মার্কেটিং বা লোক তৈরি করলে আপনার অ্যাকাউন্টও ব্যান হয়ে যাবে, ব্যালেন্স জিরো হয়ে যাবে।
💖 আমরা আপনাদের সব সময় ভালো চাই।
💡 মনে রাখবেন, এখানে কেউ আপনার কাছে টাকা চাবে না।
🌟 ভালো থাকবেন।
সকল শর্ত মেনে চললে আমাকে রিপ্লাই দিন "ইনশাআল্লাহ আমি পারবো" এটা লিখে

**শর্ত মেনে চললে নিচের বাটনে ক্লিক করুন।**""",
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

# --- CACHE MANAGER ---
# বট চালু হওয়ার সাথে সাথে একবার কনফিগারেশন লোড করবে
async def load_config_to_cache():
    global GLOBAL_CONFIG
    try:
        doc = await async_firestore_get(settings_ref)
        if doc.exists:
            data = doc.to_dict()
            GLOBAL_CONFIG.update(data)
            logger.info("Config loaded to RAM")
        else:
            # ডিফল্ট সেট করা না থাকলে তৈরি করে নিবে
            await async_firestore_set(settings_ref, GLOBAL_CONFIG)
    except Exception as e:
        logger.error(f"Config Load Error: {e}")

async def update_config_cache(key, value):
    global GLOBAL_CONFIG
    GLOBAL_CONFIG[key] = value
    # ব্যাকগ্রাউন্ডে ডাটাবেসে সেভ হবে, কিন্তু ইউজার ওয়েট করবে না
    await async_firestore_set(settings_ref, {key: value}, merge=True)

# --- STATS HELPERS ---
async def increment_stat(field):
    # ফায়ারবেস রাইট অপারেশন ব্যাকগ্রাউন্ডে পাঠানো হবে
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

# --- USER DATA HELPERS ---
async def get_user_data(user_id):
    try:
        doc = await async_firestore_get(users_ref.document(str(user_id)))
        if doc.exists:
            return doc.to_dict()
    except:
        pass
    return {"state": "IDLE", "q_index": 0, "answers": [], "passed": False}

async def update_user_data(user_id, data):
    # ইউজার ডাটা আপডেট ক্রিটিকাল, তাই await করা হবে
    await async_firestore_set(users_ref.document(str(user_id)), data)

async def delete_user_data(user_id):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(executor, lambda: users_ref.document(str(user_id)).delete())

# --- KEYBOARDS ---
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

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        chat_type = update.effective_chat.type

        if chat_type == 'private':
            # 1. অ্যাডমিন প্যানেল মেসেজ (যদি অ্যাডমিন হয়)
            if user.id in ADMIN_IDS:
                try:
                    await update.message.reply_text(
                        f"⚙️ **Admin Control Panel**\nস্বাগতম {user.first_name}!",
                        reply_markup=get_admin_menu_kb(),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except: pass # অ্যাডমিন মেসেজ ফেইল করলেও ইউজার মেসেজ যাবে

            # 2. সাধারণ ইউজার মেসেজ (সবার জন্য)
            # মেমোরি থেকে ভিডিও লিংক নেওয়া হচ্ছে (ডাটাবেস কল ছাড়াই - সুপার ফাস্ট)
            video_link = GLOBAL_CONFIG.get("video_link", "https://t.me/skyzoneit/6300")
            
            await update.message.reply_text(
                f"হ্যালো {user.first_name}! 👋\n\nSkyzone IT-তে স্বাগতম। কাজ শুরু করার জন্য আগে ভিডিওটি দেখুন:\n🎥 {video_link}\n\nভিডিও দেখা শেষ হলে নিচের বাটনে ক্লিক করে ইন্টারভিউ শুরু করুন।",
                reply_markup=get_main_menu_kb(),
                disable_web_page_preview=False
            )
        
    except Exception as e:
        logger.error(f"Start Error: {e}")
        # যদি কোনো এরর হয় তবুও যেন ইউজার রেসপন্স পায়
        await update.message.reply_text("হ্যালো! বট চালু আছে। নিচে ক্লিক করুন:", reply_markup=get_main_menu_kb())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    # বাটন ল্যাগ কমানোর জন্য আগেই answer দেওয়া হলো
    try: await query.answer()
    except: pass

    # --- ADMIN BUTTONS ---
    if data.startswith("admin_") and user_id in ADMIN_IDS:
        if data == "admin_stats":
            stats = await get_stats_safe()
            msg = f"📊 **Live Stats**\n\n" \
                  f"✅ Passed Users: {stats.get('passed_users', 0)}\n" \
                  f"📝 Interviews Started: {stats.get('total_interviews', 0)}\n" \
                  f"📅 Time: {datetime.now().strftime('%H:%M')}"
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

    # --- USER BUTTONS ---
    # ডাটাবেস রিড অপ্টিমাইজড
    user_data = await get_user_data(user_id)

    if data == "start_exam":
        if user_data.get("passed"):
            await query.edit_message_text("✅ আপনি ইতিমধ্যে ইন্টারভিউ পাস করেছেন। আপনার স্লিপ পেতে 'Slip' লিখুন।")
            return
        
        # স্ট্যাটাস আপডেট (ব্যাকগ্রাউন্ডে)
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    msg = update.message.text.strip() if update.message.text else ""
    
    # --- ADMIN INPUT ---
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

    # --- GROUP CHAT IGNORE ---
    if update.effective_chat.type != 'private':
        if msg.upper() == "IT""হ্যালো""কি কাজ""hello""Hi""আমি কাজ করতে চাই""কাজ কি""আমি নতুন""আমি গ্রুপের নতুন মেম্বার""ami group e number""Ami notun":
            await update.message.reply_text(f"{user.mention_html()}, কাজের জন্য ইনবক্সে আসুন।", parse_mode=ParseMode.HTML)
        return

    # --- USER LOGIC ---
    if msg.upper() == "IT":
        await update.message.reply_text("নিচের মেনু থেকে ইন্টারভিউ শুরু করুন:", reply_markup=get_main_menu_kb())
        return

    # ইউজারের স্টেট চেক (ডাটাবেস কল)
    user_data = await get_user_data(user_id)
    state = user_data.get("state")

    if state == "INTERVIEW":
        idx = user_data.get("q_index", 0)
        if idx >= len(QUESTIONS): idx = len(QUESTIONS) - 1
        current_q = QUESTIONS[idx]
        
        # ফাজি ম্যাচিং
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
            
            # স্ট্যাটাস আপডেট (ব্যাকগ্রাউন্ড)
            asyncio.create_task(increment_stat("passed_users"))

            form_text = f"⚡ Official Notice ⚡\n\n✅ আপনার ইন্টারভিউ সফল হয়েছে।\n📋 এখন এই ফর্মটি পূরণ করুন: <a href='{STATIC_CONFIG['form_link']}'>Form Link</a>\n\nফর্ম পূরণ শেষে আপনার স্লিপ পেতে 'Slip' লিখুন।"
            await update.message.reply_text(form_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        else:
            await update.message.reply_text(f"ভুল হয়েছে। হুবহু এটি লিখুন: `{STATIC_CONFIG['final_phrase']}`", parse_mode=ParseMode.MARKDOWN)

    elif msg.lower() == "slip":
        if not user_data.get("passed"):
            await update.message.reply_text("আপনি এখনো ইন্টারভিউ পাশ করেননি।")
            return
        
        # ক্যাশ থেকে অ্যাডমিন নাম (ফাস্ট)
        admin_user = GLOBAL_CONFIG.get("admin_username", "@SKYZONE_IT_ADMIN")

        slip = f"📄 **SKYZONE IT - RECRUITMENT SLIP**\n"
        slip += f"━━━━━━━━━━━━━━━\n"
        slip += f"👤 User: {user.first_name}\nID: <code>{user_id}</code>\n"
        slip += f"📅 Date: {datetime.now().strftime('%d/%m/%Y')}\n"
        slip += f"━━━━━━━━━━━━━━━\n"
        for item in user_data.get("answers", []):
            slip += f"• {item['a']}\n"
        slip += f"━━━━━━━━━━━━━━━\n"
        slip += f"✅ এই স্লিপটি এডমিনকে দিন: {admin_user}"
        
        await update.message.reply_text(slip, parse_mode=ParseMode.HTML)
        
        # এডমিন নোটিফিকেশন
        for adm in ADMIN_IDS:
            try: await context.bot.send_message(adm, f"🚀 New Candidate Passed!\n\n{slip}", parse_mode=ParseMode.HTML)
            except: pass

# --- POST INIT HOOK ---
async def post_init(application: Application):
    # বট চালু হওয়ার পর কনফিগারেশন লোড করবে
    await load_config_to_cache()

# --- MAIN ---
def main():
    threading.Thread(target=run_flask, daemon=True).start()
    
    # post_init যোগ করা হয়েছে যাতে বট চালুর সাথে সাথে ক্যাশ লোড হয়
    app_tg = Application.builder().token(TOKEN).post_init(post_init).build()
    
    app_tg.add_handler(CommandHandler("start", start))
    app_tg.add_handler(CommandHandler("admin", start)) # /admin দিলেও স্টার্ট হবে (এডমিনদের জন্য)
    app_tg.add_handler(CallbackQueryHandler(button_handler))
    app_tg.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Skyzone IT Bot Optimized V3 is running...")
    app_tg.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
