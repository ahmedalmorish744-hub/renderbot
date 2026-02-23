import asyncio
import re
import os
import json
import random
import sys
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- الإعدادات الأساسية ---
API_ID = int(os.environ.get('API_ID', 33957094))
API_HASH = os.environ.get('API_HASH', '35e04f65846f09700aac0696a59f1a37')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8568132127:AAG-4Mxkj7WxpQcVwUcX6GdGHRAfEMjQs_8')
ADMIN_IDS = [7853478744, 739516661]
DATA_FILE = "bot_config.json"

# --- متغيرات الحالة ---
is_posting = False
USERBOT_SESSIONS = {}
MESSAGES = {}
SETTINGS = {'post_interval': 3, 'encryption': True}
TEMP_DATA = {}

# --- إدارة البيانات ---
def load_data():
    global MESSAGES, SETTINGS
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                MESSAGES.update(data.get('messages', {}))
                SETTINGS.update(data.get('settings', SETTINGS))
        except:
            pass

def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump({'messages': MESSAGES, 'settings': SETTINGS}, f, indent=4, ensure_ascii=False)

# --- تشفير النص ---
def encrypt_text(text):
    if not SETTINGS.get('encryption'):
        return text
    zero_width_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF']
    words = text.split()
    encrypted_words = []
    for word in words:
        char_to_add = random.choice(zero_width_chars)
        pos = random.randint(0, len(word))
        new_word = word[:pos] + char_to_add + word[pos:]
        encrypted_words.append(new_word)
    return " ".join(encrypted_words)

# --- القائمة الرئيسية ---
def main_menu():
    enc_status = "✅ مفعل" if SETTINGS.get('encryption') else "❌ معطل"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة حساب", callback_data="add_account"), InlineKeyboardButton("🗑 حذف حساب", callback_data="del_account")],
        [InlineKeyboardButton("📝 ضبط الرسالة", callback_data="set_msg"), InlineKeyboardButton("⏱ ضبط الوقت", callback_data="set_time")],
        [InlineKeyboardButton("🚀 بدء النشر", callback_data="start_post"), InlineKeyboardButton("🛑 إيقاف النشر", callback_data="stop_post")],
        [InlineKeyboardButton(f"🛡 التشفير: {enc_status}", callback_data="toggle_enc"), InlineKeyboardButton("📊 الحالة", callback_data="status")],
        [InlineKeyboardButton("📢 المجموعات المشتركة", callback_data="view_chats")]
    ])

# --- إنشاء البوت ---
app = Client("pro_poster_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- معالجات البوت ---
@app.on_message(filters.user(ADMIN_IDS) & filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text(
        "👋 **أهلاً بك في البوت!**\n\n"
        "تم تفعيل صلاحيات التحكم للمسؤولين.",
        reply_markup=main_menu()
    )

@app.on_callback_query(filters.user(ADMIN_IDS))
async def cb_handler(client, query):
    global is_posting
    data = query.data
    admin_id = query.from_user.id

    if data == "status":
        status = "✅ يعمل" if is_posting else "🛑 متوقف"
        enc = "✅ مفعل" if SETTINGS.get('encryption') else "❌ معطل"
        msg = (f"📊 **حالة البوت:**\n\n"
               f"• النشر: {status}\n"
               f"• الحسابات: {len(USERBOT_SESSIONS)}\n"
               f"• التشفير: {enc}\n"
               f"• الفاصل: {SETTINGS['post_interval']} ثانية")
        await query.message.edit_text(msg, reply_markup=main_menu())
    
    elif data == "toggle_enc":
        SETTINGS['encryption'] = not SETTINGS.get('encryption')
        save_data()
        await query.message.edit_reply_markup(reply_markup=main_menu())
    
    elif data == "start_post":
        if is_posting:
            await query.answer("⚠️ النشر يعمل بالفعل!", show_alert=True)
        elif not USERBOT_SESSIONS:
            await query.answer("❌ أضف حساباً أولاً!", show_alert=True)
        elif "1" not in MESSAGES:
            await query.answer("❌ اضبط الرسالة أولاً!", show_alert=True)
        else:
            is_posting = True
            asyncio.create_task(fast_poster())
            await query.message.edit_text("🚀 بدأ النشر.", reply_markup=main_menu())
    
    elif data == "stop_post":
        is_posting = False
        await query.message.edit_text("🛑 تم الإيقاف.", reply_markup=main_menu())
    
    elif data == "add_account":
        await query.message.edit_text("📱 أرسل رقم الهاتف مع رمز الدولة.")
        TEMP_DATA[admin_id] = "awaiting_phone"
    
    elif data == "set_msg":
        await query.message.edit_text("📩 أرسل نص الإعلان الجديد.")
        TEMP_DATA[admin_id] = "awaiting_msg"
    
    elif data == "set_time":
        await query.message.edit_text("⏱ أرسل الفاصل الزمني بالثواني.")
        TEMP_DATA[admin_id] = "awaiting_time"
    
    elif data == "back_to_main":
        await query.message.edit_text("القائمة الرئيسية:", reply_markup=main_menu())

# --- معالجة النصوص ---
@app.on_message(filters.user(ADMIN_IDS) & filters.text & ~filters.command("start"))
async def text_handler(client, message):
    admin_id = message.from_user.id
    state = TEMP_DATA.get(admin_id)

    if state == "awaiting_msg":
        MESSAGES["1"] = {'text': message.text}
        save_data()
        TEMP_DATA.pop(admin_id, None)
        await message.reply_text("✅ تم حفظ الإعلان!", reply_markup=main_menu())

    elif state == "awaiting_time":
        try:
            t = int(message.text.strip())
            SETTINGS['post_interval'] = t
            save_data()
            TEMP_DATA.pop(admin_id, None)
            await message.reply_text(f"✅ تم ضبط الوقت لـ {t} ثوانٍ.", reply_markup=main_menu())
        except:
            await message.reply_text("❌ أدخل رقماً صحيحاً.")

# --- النشر ---
async def fast_poster():
    global is_posting
    while is_posting:
        if "1" not in MESSAGES or not USERBOT_SESSIONS:
            is_posting = False
            break
        raw_text = MESSAGES["1"]['text']
        for user in list(USERBOT_SESSIONS.values()):
            if not is_posting: break
            try:
                async for dialog in user.get_dialogs():
                    if not is_posting: break
                    if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                        try:
                            text_to_send = encrypt_text(raw_text)
                            await user.send_message(dialog.chat.id, text_to_send)
                            await asyncio.sleep(SETTINGS['post_interval'])
                        except FloodWait as e:
                            await asyncio.sleep(e.value)
                        except:
                            pass
            except:
                pass
        await asyncio.sleep(5)

# --- تشغيل البوت ---
def run_bot():
    """تشغيل البوت مع event loop صحيح"""
    load_data()
    
    # إنشاء event loop جديد
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # تشغيل البوت
        loop.run_until_complete(app.start())
        print("✅ البوت متصل بتليجرام")
        print("🚀 البوت يعمل الآن...")
        
        # استمرار التشغيل
        loop.run_forever()
    except KeyboardInterrupt:
        print("🛑 جاري إيقاف البوت...")
    except Exception as e:
        print(f"❌ خطأ: {e}")
    finally:
        # إيقاف البوت بشكل نظيف
        try:
            loop.run_until_complete(app.stop())
        except:
            pass
        loop.close()
        print("✅ تم إيقاف البوت")

if __name__ == "__main__":
    run_bot()
