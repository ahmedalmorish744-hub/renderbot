#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import re
import os
import random
import json
import sqlite3
import sys
import logging
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError, 
    FloodWaitError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PhoneNumberInvalidError
)
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest

# ==================== الإعدادات الأساسية ====================

API_ID = int(os.environ.get('API_ID', 33957094))
API_HASH = os.environ.get('API_HASH', "35e04f65846f09700aac0696a59f1a37")
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8617406497:AAGP7QysieblKVu_JOK8Tg9uXtb7pz7CkFA")
ADMIN_IDS = [7853478744, 8603958200]

# ==================== إعدادات التشغيل ====================

DATA_DIR = "data"
BACKUPS_DIR = "backups"
LOGS_DIR = "logs"
DB_PATH = f"{DATA_DIR}/bot_data.db"

for dir_path in [DATA_DIR, BACKUPS_DIR, LOGS_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# ==================== نظام التسجيل ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(f"{LOGS_DIR}/bot.log", encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger('Bot')

# ==================== نظام إدارة المجموعات المحظورة ====================

class GroupBlacklistManager:
    def __init__(self):
        self.banned_groups = set()
        self.failed_attempts = {}
    
    def record_failure(self, group_id, error):
        if group_id not in self.failed_attempts:
            self.failed_attempts[group_id] = 0
        self.failed_attempts[group_id] += 1
        if self.failed_attempts[group_id] >= 3:
            self.banned_groups.add(group_id)
            logger.warning(f"🚫 تم حظر المجموعة {group_id} مؤقتاً")
    
    def is_banned(self, group_id):
        return group_id in self.banned_groups
    
    def clear_banned(self, group_id):
        if group_id in self.banned_groups:
            self.banned_groups.remove(group_id)
        if group_id in self.failed_attempts:
            del self.failed_attempts[group_id]
    
    def get_banned_count(self):
        return len(self.banned_groups)

group_blacklist = GroupBlacklistManager()

# ==================== التشفير ====================

def encrypt_text(text):
    if not SETTINGS.get('encryption', True) or not text:
        return text
    invisible_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF']
    words = text.split()
    result = []
    for word in words:
        if len(word) > 2 and random.random() > 0.5:
            char = random.choice(invisible_chars)
            pos = random.randint(1, len(word)-1)
            word = word[:pos] + char + word[pos:]
        result.append(word)
    return ' '.join(result)

# ==================== قاعدة البيانات ====================

class Database:
    def __init__(self):
        self.db_path = DB_PATH
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS messages (msg_id TEXT PRIMARY KEY, content TEXT, is_active INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS accounts (phone TEXT PRIMARY KEY, session_str TEXT, status TEXT, total_posts INTEGER DEFAULT 0, success_posts INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS groups (group_id TEXT PRIMARY KEY, group_name TEXT, is_blacklisted INTEGER DEFAULT 0, post_count INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS posting_history (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, group_id TEXT, group_name TEXT, sent_at TIMESTAMP, status TEXT)''')
        conn.commit()
        conn.close()
        
        if not self.get_messages():
            self.save_message("default", "📢 مرحباً! البوت يعمل.", is_active=True)
    
    def save_setting(self, key, value):
        conn = sqlite3.connect(self.db_path)
        conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, json.dumps(value)))
        conn.commit()
        conn.close()
    
    def get_setting(self, key, default=None):
        conn = sqlite3.connect(self.db_path)
        result = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
        conn.close()
        return json.loads(result[0]) if result else default
    
    def save_message(self, msg_id, content, is_active=False):
        conn = sqlite3.connect(self.db_path)
        if is_active:
            conn.execute('UPDATE messages SET is_active = 0')
        conn.execute('INSERT OR REPLACE INTO messages (msg_id, content, is_active) VALUES (?, ?, ?)', (msg_id, content, 1 if is_active else 0))
        conn.commit()
        conn.close()
    
    def get_messages(self):
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute('SELECT msg_id, content, is_active FROM messages ORDER BY rowid DESC').fetchall()
        conn.close()
        return rows
    
    def get_active_message(self):
        conn = sqlite3.connect(self.db_path)
        row = conn.execute('SELECT msg_id, content FROM messages WHERE is_active = 1').fetchone()
        conn.close()
        if row:
            return {'id': row[0], 'content': row[1]}
        msgs = self.get_messages()
        if msgs:
            self.set_active_message(msgs[0][0])
            return {'id': msgs[0][0], 'content': msgs[0][1]}
        return None
    
    def set_active_message(self, msg_id):
        conn = sqlite3.connect(self.db_path)
        conn.execute('UPDATE messages SET is_active = 0')
        conn.execute('UPDATE messages SET is_active = 1 WHERE msg_id = ?', (msg_id,))
        conn.commit()
        conn.close()
    
    def delete_message(self, msg_id):
        conn = sqlite3.connect(self.db_path)
        conn.execute('DELETE FROM messages WHERE msg_id = ?', (msg_id,))
        conn.commit()
        conn.close()
    
    def add_account(self, phone, session_str):
        conn = sqlite3.connect(self.db_path)
        conn.execute('INSERT OR REPLACE INTO accounts (phone, session_str, status) VALUES (?, ?, ?)', (phone, session_str, 'active'))
        conn.commit()
        conn.close()
    
    def remove_account(self, phone):
        conn = sqlite3.connect(self.db_path)
        conn.execute('DELETE FROM accounts WHERE phone = ?', (phone,))
        conn.commit()
        conn.close()
    
    def get_accounts(self):
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute('SELECT phone, status, total_posts, success_posts FROM accounts').fetchall()
        conn.close()
        return rows
    
    def get_account_session(self, phone):
        conn = sqlite3.connect(self.db_path)
        result = conn.execute('SELECT session_str FROM accounts WHERE phone = ?', (phone,)).fetchone()
        conn.close()
        return result[0] if result else None
    
    def increment_posts(self, phone, success=True):
        conn = sqlite3.connect(self.db_path)
        if success:
            conn.execute('UPDATE accounts SET total_posts = total_posts + 1, success_posts = success_posts + 1 WHERE phone = ?', (phone,))
        else:
            conn.execute('UPDATE accounts SET total_posts = total_posts + 1 WHERE phone = ?', (phone,))
        conn.commit()
        conn.close()
    
    def blacklist_group(self, group_id, group_name=""):
        conn = sqlite3.connect(self.db_path)
        conn.execute('INSERT OR REPLACE INTO groups (group_id, group_name, is_blacklisted) VALUES (?, ?, 1)', (str(group_id), group_name[:50]))
        conn.commit()
        conn.close()
    
    def whitelist_group(self, group_id):
        conn = sqlite3.connect(self.db_path)
        conn.execute('DELETE FROM groups WHERE group_id = ?', (str(group_id),))
        conn.commit()
        conn.close()
    
    def get_blacklisted_groups(self):
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute('SELECT group_id, group_name FROM groups WHERE is_blacklisted = 1').fetchall()
        conn.close()
        return rows
    
    def update_group_post(self, group_id):
        conn = sqlite3.connect(self.db_path)
        conn.execute('UPDATE groups SET post_count = post_count + 1 WHERE group_id = ?', (str(group_id),))
        conn.commit()
        conn.close()
    
    def log_post(self, phone, group_id, group_name, status='success'):
        conn = sqlite3.connect(self.db_path)
        conn.execute('INSERT INTO posting_history (phone, group_id, group_name, sent_at, status) VALUES (?, ?, ?, ?, ?)', 
                    (phone, str(group_id), group_name[:50], datetime.now(), status))
        if status == 'success':
            self.increment_posts(phone, True)
            self.update_group_post(group_id)
        else:
            self.increment_posts(phone, False)
        conn.commit()
        conn.close()
    
    def get_stats(self, hours=24):
        since = datetime.now() - timedelta(hours=hours)
        conn = sqlite3.connect(self.db_path)
        total = conn.execute('SELECT COUNT(*) FROM posting_history WHERE sent_at > ?', (since,)).fetchone()[0]
        success = conn.execute("SELECT COUNT(*) FROM posting_history WHERE sent_at > ? AND status = 'success'", (since,)).fetchone()[0]
        conn.close()
        return {'total': total, 'success': success}
    
    def get_recent_posts(self, limit=10):
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute('SELECT phone, group_name, status, sent_at FROM posting_history ORDER BY sent_at DESC LIMIT ?', (limit,)).fetchall()
        conn.close()
        return rows
    
    def get_total_groups_count(self):
        conn = sqlite3.connect(self.db_path)
        count = conn.execute('SELECT COUNT(*) FROM groups').fetchone()[0]
        conn.close()
        return count

db = Database()

# ==================== المتغيرات العامة ====================

USER_CLIENTS = {}
SETTINGS = {
    'interval': 3, 
    'encryption': True, 
    'auto_join_enabled': True
}
TEMP = {}
is_posting = False
bot = None
start_time = datetime.now()

# ==================== الأزرار ====================

def main_buttons():
    enc_status = "✅" if SETTINGS['encryption'] else "❌"
    return [
        [Button.inline("➕ إضافة حساب", b"add"), Button.inline("🗑 حذف حساب", b"del_list")],
        [Button.inline("📝 إدارة الرسائل", b"manage_messages"), Button.inline("⏱ ضبط الوقت", b"time")],
        [Button.inline("🚀 بدء النشر", b"start_p"), Button.inline("🛑 إيقاف النشر", b"stop_p")],
        [Button.inline(f"🛡 التشفير: {enc_status}", b"toggle_enc"), Button.inline("📊 الحالة", b"status")],
        [Button.inline("🚫 إدارة المحظورات", b"blacklist_menu"), Button.inline("⚙️ إعدادات", b"advanced")]
    ]

def messages_buttons():
    return [
        [Button.inline("📋 عرض الرسائل", b"list_messages")],
        [Button.inline("➕ إضافة رسالة", b"add_message")],
        [Button.inline("✅ تعيين رسالة نشطة", b"set_active_message")],
        [Button.inline("🗑 حذف رسالة", b"delete_message")],
        [Button.inline("⬅️ عودة", b"back")]
    ]

def blacklist_buttons():
    return [
        [Button.inline("➕ إضافة للمحظورات", b"add_blacklist")],
        [Button.inline("➖ إزالة من المحظورات", b"remove_blacklist")],
        [Button.inline("📋 عرض المحظورات", b"view_blacklist")],
        [Button.inline("⬅️ عودة", b"advanced")]
    ]

def advanced_buttons():
    auto_join = "✅" if SETTINGS.get('auto_join_enabled', True) else "❌"
    return [
        [Button.inline(f"🤖 انضمام تلقائي {auto_join}", b"toggle_autojoin")],
        [Button.inline("💾 نسخ احتياطي", b"backup")],
        [Button.inline("📊 إحصائيات", b"detailed_stats")],
        [Button.inline("⬅️ عودة", b"back")]
    ]

# ==================== المعالجات ====================

async def start_handler(event):
    if event.sender_id not in ADMIN_IDS:
        await event.respond("❌ غير مصرح لك!")
        return
    
    accounts = db.get_accounts()
    groups_count = db.get_total_groups_count()
    active_msg = db.get_active_message()
    
    await event.respond(
        f"👋 **أهلاً بك في البوت!**\n\n"
        f"📊 **الإحصائيات:**\n"
        f"• الحسابات: {len(accounts)}\n"
        f"• المجموعات: {groups_count}\n"
        f"📨 **الرسالة النشطة:**\n{active_msg['content'][:100] if active_msg else 'لا توجد'}\n\n"
        f"استخدم الأزرار:", 
        buttons=main_buttons()
    )

async def callback_handler(event):
    global SETTINGS, is_posting
    
    if event.sender_id not in ADMIN_IDS:
        return
    
    data = event.data.decode()
    
    if data == "status":
        await show_status(event)
    elif data == "add":
        await event.edit("📱 أرسل رقم الهاتف مع رمز الدولة:\nمثال: +967712345678")
        TEMP[event.sender_id] = "phone"
    elif data == "del_list":
        await show_delete_list(event)
    elif data.startswith("rm_"):
        await delete_account(event, data[3:])
    elif data == "time":
        await event.edit("⏱ أرسل الفاصل الزمني (1-60 ثانية):")
        TEMP[event.sender_id] = "time"
    elif data == "toggle_enc":
        SETTINGS['encryption'] = not SETTINGS['encryption']
        db.save_setting('encryption', SETTINGS['encryption'])
        await event.answer(f"✅ التشفير {'مفعل' if SETTINGS['encryption'] else 'معطل'}")
        await event.edit("👋 لوحة التحكم:", buttons=main_buttons())
    elif data == "toggle_autojoin":
        SETTINGS['auto_join_enabled'] = not SETTINGS.get('auto_join_enabled', True)
        db.save_setting('auto_join_enabled', SETTINGS['auto_join_enabled'])
        await event.answer(f"✅ الانضمام التلقائي {'مفعل' if SETTINGS['auto_join_enabled'] else 'معطل'}")
        await event.edit("⚙️ الإعدادات:", buttons=advanced_buttons())
    elif data == "advanced":
        await event.edit("⚙️ الإعدادات المتقدمة", buttons=advanced_buttons())
    elif data == "back":
        await event.edit("👋 لوحة التحكم", buttons=main_buttons())
    elif data == "backup":
        await create_backup(event)
    elif data == "detailed_stats":
        await show_detailed_stats(event)
    elif data == "blacklist_menu":
        await event.edit("🚫 إدارة المحظورات", buttons=blacklist_buttons())
    elif data == "view_blacklist":
        await show_blacklist(event)
    elif data == "add_blacklist":
        await event.edit("🚫 أرسل معرف المجموعة لحظرها:")
        TEMP[event.sender_id] = "add_blacklist"
    elif data == "remove_blacklist":
        await show_remove_blacklist(event)
    elif data.startswith("unblack_"):
        await remove_blacklist(event, data[8:])
    elif data == "manage_messages":
        await event.edit("📝 إدارة الرسائل", buttons=messages_buttons())
    elif data == "list_messages":
        await list_messages(event)
    elif data == "add_message":
        await event.edit("📝 أرسل نص الرسالة:")
        TEMP[event.sender_id] = "new_message"
    elif data == "set_active_message":
        await show_set_active(event)
    elif data.startswith("set_active_"):
        db.set_active_message(data[11:])
        await event.answer("✅ تم تعيين الرسالة كنشطة")
        await event.edit("📝 إدارة الرسائل", buttons=messages_buttons())
    elif data == "delete_message":
        await show_delete_message(event)
    elif data.startswith("del_msg_"):
        db.delete_message(data[8:])
        await event.answer("✅ تم حذف الرسالة")
        await event.edit("📝 إدارة الرسائل", buttons=messages_buttons())
    elif data == "start_p":
        if not USER_CLIENTS:
            return await event.answer("❌ لا توجد حسابات!", alert=True)
        if not db.get_active_message():
            return await event.answer("❌ لا توجد رسالة نشطة!", alert=True)
        if is_posting:
            return await event.answer("⚠️ النشر يعمل بالفعل!", alert=True)
        is_posting = True
        asyncio.create_task(poster())
        await event.edit("🚀 بدأ النشر!", buttons=main_buttons())
    elif data == "stop_p":
        is_posting = False
        await event.edit("🛑 توقف النشر", buttons=main_buttons())

async def show_status(event):
    accounts = db.get_accounts()
    stats = db.get_stats(24)
    uptime = datetime.now() - start_time
    hours = int(uptime.total_seconds() // 3600)
    minutes = int((uptime.total_seconds() % 3600) // 60)
    active_accounts = len([a for a in accounts if a[1] == 'active'])
    
    text = f"📊 **حالة البوت**\n\n"
    text += f"⏰ وقت التشغيل: {hours} س {minutes} د\n"
    text += f"👤 الحسابات: {active_accounts}/{len(accounts)}\n"
    text += f"📨 آخر 24 ساعة: {stats['total']}\n"
    text += f"✅ الناجح: {stats['success']}\n"
    text += f"⚙️ الفاصل: {SETTINGS['interval']} ثانية\n"
    text += f"🔄 النشر: {'🟢 نشط' if is_posting else '🔴 متوقف'}"
    
    await event.edit(text, buttons=main_buttons())

async def show_detailed_stats(event):
    accounts = db.get_accounts()
    text = "📊 **إحصائيات الحسابات**\n\n"
    for phone, status, total, success in accounts[:10]:
        rate = (success / total * 100) if total > 0 else 0
        icon = "🟢" if status == 'active' else "🔴"
        text += f"{icon} {phone[-8:]}: {total} منشور ({rate:.0f}%)\n"
    
    recent = db.get_recent_posts(5)
    text += f"\n📋 **آخر النشاطات:**\n"
    for phone, group, status, sent_at in recent:
        time_str = datetime.fromisoformat(sent_at).strftime('%H:%M')
        icon = "✅" if status == 'success' else "❌"
        text += f"{icon} {time_str} - {group[:20]}\n"
    
    await event.edit(text, buttons=advanced_buttons())

async def list_messages(event):
    msgs = db.get_messages()
    if not msgs:
        await event.edit("📭 لا توجد رسائل", buttons=messages_buttons())
        return
    
    text = "📋 **الرسائل:**\n\n"
    for msg_id, content, active in msgs[:10]:
        star = "🌟" if active else "📄"
        preview = content[:35] + "..." if len(content) > 35 else content
        text += f"{star} `{preview}`\n🆔 {msg_id}\n\n"
    
    await event.edit(text, buttons=messages_buttons())

async def show_set_active(event):
    msgs = db.get_messages()
    if not msgs:
        return await event.answer("❌ لا توجد رسائل", alert=True)
    
    btns = []
    for msg_id, content, active in msgs[:10]:
        preview = content[:20] + "..." if len(content) > 20 else content
        btns.append([Button.inline(f"{'🌟' if active else '📄'} {preview}", f"set_active_{msg_id}".encode())])
    btns.append([Button.inline("⬅️ عودة", b"manage_messages")])
    await event.edit("✅ اختر الرسالة النشطة:", buttons=btns)

async def show_delete_message(event):
    msgs = db.get_messages()
    if not msgs:
        return await event.answer("❌ لا توجد رسائل", alert=True)
    
    btns = []
    for msg_id, content, active in msgs[:10]:
        preview = content[:20] + "..." if len(content) > 20 else content
        btns.append([Button.inline(f"🗑 {preview}", f"del_msg_{msg_id}".encode())])
    btns.append([Button.inline("⬅️ عودة", b"manage_messages")])
    await event.edit("🗑 اختر رسالة للحذف:", buttons=btns)

async def show_delete_list(event):
    acc = db.get_accounts()
    if not acc:
        return await event.answer("❌ لا توجد حسابات", alert=True)
    
    btns = []
    for phone, status, total, success in acc[:10]:
        short = phone[-8:]
        btns.append([Button.inline(f"🗑 {short} ({total})", f"rm_{phone}".encode())])
    btns.append([Button.inline("⬅️ عودة", b"back")])
    await event.edit("🗑 اختر حساباً للحذف:", buttons=btns)

async def delete_account(event, phone):
    if phone in USER_CLIENTS:
        await USER_CLIENTS[phone].disconnect()
        del USER_CLIENTS[phone]
    db.remove_account(phone)
    await event.answer(f"✅ تم حذف {phone}", alert=True)
    await show_delete_list(event)

async def show_blacklist(event):
    bl = db.get_blacklisted_groups()
    if not bl:
        await event.edit("📭 لا توجد مجموعات محظورة", buttons=blacklist_buttons())
        return
    
    text = "🚫 **المجموعات المحظورة:**\n\n"
    for gid, name in bl[:20]:
        text += f"• {name[:30] if name else gid}\n🆔 {gid}\n\n"
    await event.edit(text, buttons=blacklist_buttons())

async def show_remove_blacklist(event):
    bl = db.get_blacklisted_groups()
    if not bl:
        return await event.answer("❌ لا توجد محظورات", alert=True)
    
    btns = []
    for gid, name in bl[:10]:
        btns.append([Button.inline(f"✅ {name[:15] if name else gid[:10]}", f"unblack_{gid}".encode())])
    btns.append([Button.inline("⬅️ عودة", b"blacklist_menu")])
    await event.edit("✅ اختر مجموعة للإزالة:", buttons=btns)

async def remove_blacklist(event, group_id):
    db.whitelist_group(group_id)
    group_blacklist.clear_banned(str(group_id))
    await event.answer("✅ تمت الإزالة", alert=True)
    await show_blacklist(event)

async def create_backup(event):
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"{BACKUPS_DIR}/backup_{timestamp}.db"
        shutil.copy2(DB_PATH, backup_file)
        await event.answer(f"✅ تم إنشاء النسخة: {backup_file}", alert=True)
    except Exception as e:
        await event.answer(f"❌ فشل النسخ: {e}", alert=True)

# ===== معالج النصوص =====

async def text_handler(event):
    uid = event.sender_id
    if uid not in ADMIN_IDS:
        return
    
    state = TEMP.get(uid)
    text = event.message.text.strip()
    
    if state == "new_message":
        db.save_message(f"msg_{int(time.time())}", text)
        TEMP.pop(uid)
        await event.respond("✅ تم إضافة الرسالة!", buttons=messages_buttons())
    elif state == "phone":
        await handle_phone(event, text, uid)
    elif state == "add_blacklist":
        db.blacklist_group(text, text)
        TEMP.pop(uid)
        await event.respond(f"✅ تم حظر {text}", buttons=blacklist_buttons())
    elif state == "time":
        try:
            val = int(text)
            if 1 <= val <= 60:
                SETTINGS['interval'] = val
                db.save_setting('interval', val)
                TEMP.pop(uid)
                await event.respond(f"✅ تم ضبط الوقت على {val} ثانية", buttons=main_buttons())
            else:
                await event.respond("❌ الرجاء إدخال قيمة بين 1 و 60")
        except:
            await event.respond("❌ أرسل رقماً فقط")
    else:
        links = re.findall(r"https?://t\.me/[a-zA-Z0-9_]+", text)
        if links and SETTINGS.get('auto_join_enabled', True) and USER_CLIENTS:
            await handle_auto_join(event, links)

# ===== دوال تسجيل الدخول =====

async def handle_phone(event, phone, uid):
    try:
        if not phone.startswith('+'):
            phone = '+' + phone
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        await client.send_code_request(phone)
        TEMP[uid] = {"state": "code", "phone": phone, "client": client}
        await event.respond(f"📩 تم إرسال كود التحقق إلى {phone}\nأرسل الكود:")
    except Exception as e:
        await event.respond(f"❌ خطأ: {str(e)[:100]}")

async def handle_code(event, code, uid):
    state = TEMP[uid]
    try:
        await state["client"].sign_in(state["phone"], code)
        session_str = state["client"].session.save()
        db.add_account(state["phone"], session_str)
        USER_CLIENTS[state["phone"]] = state["client"]
        TEMP.pop(uid)
        await event.respond(f"✅ تم تفعيل الحساب {state['phone']}!")
    except SessionPasswordNeededError:
        TEMP[uid] = {"state": "password", "phone": state["phone"], "client": state["client"]}
        await event.respond("🔐 يتطلب الحساب كلمة مرور (2FA)\nأرسل كلمة المرور:")
    except Exception as e:
        await event.respond(f"❌ فشل: {str(e)[:100]}")

async def handle_password(event, password, uid):
    state = TEMP[uid]
    try:
        await state["client"].sign_in(password=password)
        session_str = state["client"].session.save()
        db.add_account(state["phone"], session_str)
        USER_CLIENTS[state["phone"]] = state["client"]
        TEMP.pop(uid)
        await event.respond(f"✅ تم تفعيل الحساب {state['phone']}!")
    except Exception as e:
        await event.respond(f"❌ خطأ: {str(e)[:100]}")

# ===== دالة الانضمام =====

async def handle_auto_join(event, links):
    await event.respond(f"🐢 جاري الانضمام إلى {len(links)} رابط...")
    success = 0
    for link in links[:3]:
        for phone, client in USER_CLIENTS.items():
            try:
                if "joinchat" in link:
                    hash_part = link.split('/')[-1]
                    await client(ImportChatInviteRequest(hash_part))
                else:
                    await client(JoinChannelRequest(link))
                success += 1
                break
            except:
                continue
        await asyncio.sleep(random.randint(30, 60))
    await event.respond(f"✅ تم الانضمام إلى {success} رابط")

# ===== دالة النشر =====

async def poster():
    global is_posting
    while is_posting:
        try:
            if not USER_CLIENTS:
                await asyncio.sleep(5)
                continue
            
            active = db.get_active_message()
            if not active:
                await asyncio.sleep(5)
                continue
            
            txt = encrypt_text(active['content'])
            
            for phone, client in USER_CLIENTS.items():
                if not is_posting:
                    break
                
                try:
                    async for dialog in client.iter_dialogs():
                        if not is_posting:
                            break
                        if dialog.is_group:
                            bl = [g[0] for g in db.get_blacklisted_groups()]
                            if str(dialog.id) in bl:
                                continue
                            if group_blacklist.is_banned(str(dialog.id)):
                                continue
                            
                            try:
                                await client.send_message(dialog.id, txt)
                                db.log_post(phone, dialog.id, dialog.name, 'success')
                                group_blacklist.clear_banned(str(dialog.id))
                                await asyncio.sleep(SETTINGS['interval'])
                            except FloodWaitError as e:
                                await asyncio.sleep(e.seconds)
                            except Exception as e:
                                db.log_post(phone, dialog.id, dialog.name, 'failed')
                                if "banned" in str(e).lower():
                                    group_blacklist.record_failure(str(dialog.id), str(e))
                except:
                    continue
            await asyncio.sleep(5)
        except:
            await asyncio.sleep(5)

# ===== استعادة الجلسات =====

async def restore_sessions():
    for acc in db.get_accounts():
        try:
            phone = acc[0]
            session_str = db.get_account_session(phone)
            if session_str:
                client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
                await client.connect()
                if await client.is_user_authorized():
                    USER_CLIENTS[phone] = client
                    logger.info(f"✅ تم استعادة الحساب: {phone}")
        except:
            pass

# ===== التشغيل الرئيسي =====

async def main():
    global bot, start_time
    start_time = datetime.now()
    
    print("="*50)
    print("🚀 جاري تشغيل البوت...")
    print(f"👤 المشرفون: {ADMIN_IDS}")
    print("="*50)
    
    await restore_sessions()
    
    bot = TelegramClient('bot_session', API_ID, API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    
    me = await bot.get_me()
    print(f"✅ البوت متصل: @{me.username}")
    print("🎉 البوت جاهز! أرسل /start")
    
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_e(e): await start_handler(e)
    
    @bot.on(events.CallbackQuery())
    async def callback_e(e): await callback_handler(e)
    
    @bot.on(events.NewMessage)
    async def text_e(e):
        if e.message.text and e.sender_id in ADMIN_IDS:
            state = TEMP.get(e.sender_id)
            if isinstance(state, dict) and state.get('state') == 'code':
                await handle_code(e, e.message.text.strip(), e.sender_id)
            elif isinstance(state, dict) and state.get('state') == 'password':
                await handle_password(e, e.message.text.strip(), e.sender_id)
            else:
                await text_handler(e)
        elif e.message.text and SETTINGS.get('auto_join_enabled', True) and USER_CLIENTS:
            links = re.findall(r"https?://t\.me/[a-zA-Z0-9_]+", e.message.text)
            if links:
                await handle_auto_join(e, links)
    
    await bot.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 تم إيقاف البوت")
    except Exception as e:
        print(f"❌ خطأ: {e}")
        time.sleep(5)
        os.execl(sys.executable, sys.executable, *sys.argv)
