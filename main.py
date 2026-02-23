import asyncio
import re
import os
import json
import random
from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait, RPCError, BadRequest, SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

# --- الإعدادات الأساسية (استخدام متغيرات البيئة للأمان) ---
API_ID = int(os.environ.get('API_ID', 33957094))
API_HASH = os.environ.get('API_HASH', '35e04f65846f09700aac0696a59f1a37')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8568132127:AAG-4Mxkj7WxpQcVwUcX6GdGHRAfEMjQs_8')
ADMIN_IDS = [7853478744, 739516661]
DATA_FILE = "bot_config.json"

# --- تعريف كائن البوت ---
app = Client("pro_poster_ultimate_fixed", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- متغيرات الحالة ---
is_posting = False
USERBOT_SESSIONS = {} 
MESSAGES = {} 
SETTINGS = {
    'post_interval': 3,
    'encryption': True 
} 
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
        except: pass

def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump({'messages': MESSAGES, 'settings': SETTINGS}, f, indent=4, ensure_ascii=False)

# --- دالة تشفير النص (Anti-Spam) ---
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

# --- واجهة الأزرار الرئيسية ---
def main_menu():
    enc_status = "✅ مفعل" if SETTINGS.get('encryption') else "❌ معطل"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة حساب", callback_data="add_account"), InlineKeyboardButton("🗑 حذف حساب", callback_data="del_account")],
        [InlineKeyboardButton("📝 ضبط الرسالة", callback_data="set_msg"), InlineKeyboardButton("⏱ ضبط الوقت", callback_data="set_time")],
        [InlineKeyboardButton("🚀 بدء النشر", callback_data="start_post"), InlineKeyboardButton("🛑 إيقاف النشر", callback_data="stop_post")],
        [InlineKeyboardButton(f"🛡 التشفير: {enc_status}", callback_data="toggle_enc"), InlineKeyboardButton("📊 الحالة", callback_data="status")],
        [InlineKeyboardButton("📢 المجموعات المشتركة", callback_data="view_chats")]
    ])

# --- معالجات البوت ---
@app.on_message(filters.user(ADMIN_IDS) & filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text(
        "👋 **أهلاً بك في النسخة المصلحة والنهائية!**\n\n"
        "تم تفعيل صلاحيات التحكم لكلا المسؤولين.",
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
        msg = (f"📊 **حالة البوت الحالية:**\n\n"
               f"• النشر: {status}\n"
               f"• الحسابات النشطة: {len(USERBOT_SESSIONS)}\n"
               f"• التشفير: {enc}\n"
               f"• الفاصل الزمني: {SETTINGS['post_interval']} ثانية")
        await query.message.edit_text(msg, reply_markup=main_menu())

    elif data == "add_account":
        await query.message.edit_text("📱 أرسل رقم الهاتف مع رمز الدولة.\nمثال: `+967738473371`")
        TEMP_DATA[admin_id] = "awaiting_phone"

    elif data == "del_account":
        if not USERBOT_SESSIONS:
            await query.answer("❌ لا توجد حسابات لحذفها.", show_alert=True)
            return
        buttons = []
        for phone in USERBOT_SESSIONS.keys():
            buttons.append([InlineKeyboardButton(f"❌ حذف {phone}", callback_data=f"remove_{phone}")])
        buttons.append([InlineKeyboardButton("⬅️ عودة", callback_data="back_to_main")])
        await query.message.edit_text("🗑 اختر الحساب الذي تريد حذفه:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("remove_"):
        phone = data.replace("remove_", "")
        if phone in USERBOT_SESSIONS:
            try:
                await USERBOT_SESSIONS[phone].stop()
                del USERBOT_SESSIONS[phone]
                session_file = f"session_{phone}.session"
                if os.path.exists(session_file):
                    os.remove(session_file)
                await query.answer(f"✅ تم حذف {phone}.", show_alert=True)
            except: pass
        await cb_handler(client, query)

    elif data == "back_to_main":
        await query.message.edit_text("👋 لوحة التحكم الرئيسية:", reply_markup=main_menu())

    elif data == "toggle_enc":
        SETTINGS['encryption'] = not SETTINGS.get('encryption')
        save_data()
        await query.message.edit_reply_markup(reply_markup=main_menu())

    elif data == "set_msg":
        await query.message.edit_text("📩 أرسل نص الإعلان الجديد.")
        TEMP_DATA[admin_id] = "awaiting_msg"

    elif data == "set_time":
        await query.message.edit_text("⏱ أرسل الفاصل الزمني بالثواني.")
        TEMP_DATA[admin_id] = "awaiting_time"

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
            await query.message.edit_text("🚀 بدأ النشر بنجاح.", reply_markup=main_menu())

    elif data == "stop_post":
        is_posting = False
        await query.message.edit_text("🛑 تم إيقاف النشر.", reply_markup=main_menu())

    elif data == "view_chats":
        if not USERBOT_SESSIONS:
            await query.answer("❌ لا توجد حسابات.", show_alert=True)
            return
        await query.answer("جاري جلب قائمة المجموعات...", show_alert=False)
        chat_info = "📢 **المجموعات المشتركة:**\n"
        count = 0
        for user in USERBOT_SESSIONS.values():
            async for dialog in user.get_dialogs():
                if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                    count += 1
                    if count <= 15: chat_info += f"- {dialog.chat.title}\n"
        chat_info += f"\n✅ الإجمالي: {count} مجموعة."
        await query.message.edit_text(chat_info, reply_markup=main_menu())

# --- معالجة الرسائل النصية ---
@app.on_message(filters.user(ADMIN_IDS) & filters.text & ~filters.command("start"))
async def text_handler(client, message):
    admin_id = message.from_user.id
    state = TEMP_DATA.get(admin_id)

    links = re.findall(r"(https?://t\.me/(?:\+|joinchat/)?[\w-]+)", message.text)
    if links:
        if not USERBOT_SESSIONS:
            await message.reply_text("❌ أضف حساباً أولاً.")
            return
        await message.reply_text(f"⏳ جاري الانضمام لـ {len(links)} مجموعة...")
        for link in links:
            for user in USERBOT_SESSIONS.values():
                try: 
                    await user.join_chat(link)
                    await asyncio.sleep(2)
                except: pass
        await message.reply_text("✅ انتهى الانضمام.")
        return

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
        except: await message.reply_text("❌ أدخل رقماً صحيحاً.")

    elif state == "awaiting_phone":
        phone = message.text.strip()
        session_name = f"session_{phone}"
        new_client = Client(session_name, api_id=API_ID, api_hash=API_HASH)
        await new_client.connect()
        try:
            await asyncio.sleep(1)
            code_info = await new_client.send_code(phone)
            TEMP_DATA[admin_id] = {"state": "awaiting_code", "phone": phone, "hash": code_info.phone_code_hash, "client": new_client}
            await message.reply_text(f"📩 تم إرسال الكود لـ {phone}.\nتفقد تطبيق Telegram في هاتفك وأرسل الكود هنا.")
        except Exception as e: 
            await message.reply_text(f"❌ فشل إرسال الكود: {e}")
            await new_client.disconnect()

    elif isinstance(state, dict) and state.get("state") == "awaiting_code":
        try:
            code = message.text.strip()
            await state["client"].sign_in(state["phone"], state["hash"], code)
            USERBOT_SESSIONS[state["phone"]] = state["client"]
            await message.reply_text(f"✅ تم تفعيل الحساب {state['phone']} بنجاح!")
            TEMP_DATA.pop(admin_id, None)
        except SessionPasswordNeeded:
            TEMP_DATA[admin_id]["state"] = "awaiting_password"
            await message.reply_text("🔐 أرسل كلمة سر التحقق بخطوتين.")
        except (PhoneCodeInvalid, PhoneCodeExpired):
            await message.reply_text("❌ الكود غير صحيح أو انتهت صلاحيته. حاول مرة أخرى.")
        except Exception as e: 
            await message.reply_text(f"❌ خطأ: {e}")
            TEMP_DATA.pop(admin_id, None)

    elif isinstance(state, dict) and state.get("state") == "awaiting_password":
        try:
            await state["client"].check_password(message.text.strip())
            USERBOT_SESSIONS[state["phone"]] = state["client"]
            await message.reply_text(f"✅ تم التفعيل بنجاح!")
            TEMP_DATA.pop(admin_id, None)
        except Exception as e: await message.reply_text(f"❌ كلمة السر غير صحيحة: {e}")

# --- دالة النشر الأساسية ---
async def fast_poster():
    global is_posting
    while is_posting:
        if "1" not in MESSAGES or not USERBOT_SESSIONS:
            is_posting = False
            break
        raw_text = MESSAGES["1"]['text']
        for phone, user in list(USERBOT_SESSIONS.items()):
            if not is_posting: break
            try:
                async for dialog in user.get_dialogs():
                    if not is_posting: break
                    if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                        try:
                            text_to_send = encrypt_text(raw_text)
                            await user.send_message(dialog.chat.id, text_to_send)
                            await asyncio.sleep(SETTINGS['post_interval'])
                        except FloodWait as e: await asyncio.sleep(e.value)
                        except: pass
            except: pass
        await asyncio.sleep(5)

# --- تشغيل البوت وتحميل الجلسات القديمة ---
async def load_existing_sessions():
    for file in os.listdir("."):
        if file.endswith(".session") and file.startswith("session_"):
            phone = file.replace(".session", "").replace("session_", "")
            try:
                c = Client(file.replace(".session", ""), api_id=API_ID, api_hash=API_HASH)
                await c.start()
                USERBOT_SESSIONS[phone] = c
                print(f"✅ تم تحميل الحساب: {phone}")
            except: pass

# --- التعديل المهم: إصلاح مشكلة event loop ---
if __name__ == "__main__":
    # تحميل البيانات
    load_data()
    
    # إنشاء event loop جديد
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # تشغيل البوت
        loop.run_until_complete(app.start())
        loop.run_until_complete(load_existing_sessions())
        print("🚀 البوت المصلح يعمل الآن...")
        
        # استمرار التشغيل
        loop.run_forever()
    except KeyboardInterrupt:
        print("🛑 تم إيقاف البوت")
    finally:
        # إيقاف البوت بشكل نظيف
        loop.run_until_complete(app.stop())
        loop.close()
