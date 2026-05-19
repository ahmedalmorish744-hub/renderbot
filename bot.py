#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════╗
║     🤖 بوت النشر الخارق - النسخة النهائية 🚀                 ║
║     مع Procfile + Web Service + Worker                       ║
╚═══════════════════════════════════════════════════════════════╝
"""

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
import threading
from datetime import datetime, timedelta
from pathlib import Path
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from flask import Flask, jsonify
from threading import Thread

# ==================== الإعدادات الأساسية ====================

API_ID = int(os.environ.get('API_ID', 33957094))
API_HASH = os.environ.get('API_HASH', "35e04f65846f09700aac0696a59f1a37")
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8568132127:AAG-4Mxkj7WxpQcVwUcX6GdGHRAfEMjQs_8")
ADMIN_ID = int(os.environ.get('ADMIN_ID', 7853478744))

# ==================== إعدادات التشغيل ====================

DATA_DIR = "data"
BACKUPS_DIR = "backups"
LOGS_DIR = "logs"
DB_PATH = f"{DATA_DIR}/bot_data.db"

for dir_path in [DATA_DIR, BACKUPS_DIR, LOGS_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# ==================== قفل قاعدة البيانات ====================
db_lock = threading.Lock()

# ==================== خادم الويب ====================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'bot': 'Telegram Poster Bot',
        'version': '4.0',
        'time': str(datetime.now()),
        'accounts': len(USER_CLIENTS) if 'USER_CLIENTS' in globals() else 0,
        'is_posting': is_posting if 'is_posting' in globals() else False
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

def run_web():
    """تشغيل خادم الويب - يفتح المنفذ تلقائياً"""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ==================== نظام التسجيل ====================

class Logger:
    def __init__(self):
        log_file = f"{LOGS_DIR}/bot_{datetime.now().strftime('%Y%m%d')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(log_file, encoding='utf-8'), logging.StreamHandler()]
        )
        self.logger = logging.getLogger('Bot')
    
    def info(self, msg): self.logger.info(msg); print(f"ℹ️ {msg}")
    def warning(self, msg): self.logger.warning(msg); print(f"⚠️ {msg}")
    def error(self, msg): self.logger.error(msg); print(f"❌ {msg}")
    def success(self, msg): self.logger.info(f"✅ {msg}"); print(f"✅ {msg}")
    def critical(self, msg): self.logger.critical(msg); print(f"💥 {msg}")

logger = Logger()

# ==================== نظام التشفير ====================

class AdvancedEncryption:
    def __init__(self):
        self.invisible_chars = ['\u200B', '\u200C', '\u200D']
        self.link_patterns = [(r't\.me', 't\u200B.me'), (r'@', '@\u200B')]
    
    def encrypt_smart(self, text):
        result = text
        for pattern, replacement in self.link_patterns:
            result = re.sub(pattern, replacement, result)
        if len(text) > 50 and random.random() > 0.7:
            words = result.split()
            for i in range(len(words)):
                if random.random() > 0.9:
                    pos = random.randint(1, max(1, len(words[i])-1))
                    words[i] = words[i][:pos] + random.choice(self.invisible_chars) + words[i][pos:]
            result = ' '.join(words)
        return result

advanced_encryption = AdvancedEncryption()

def encrypt_text(text):
    if not SETTINGS.get('encryption', True):
        return text
    return advanced_encryption.encrypt_smart(text)

# ==================== كلاس مكافحة الاكتشاف ====================

class AntiDetection:
    def __init__(self):
        self.posted_messages = {}
        self.last_posts = {}
        self.warmed_groups = set()
        
        self.synonyms = {
            'اشترك': ['انضم', 'تابع', 'كن معنا'],
            'قناة': ['مجموعة', 'منصة', 'صفحتنا'],
            'دعم': ['مساندة', 'متابعة'],
        }
        
        self.templates = [
            "{}", "✨ {} ✨", "🔹 {}\n🔸 تابعنا للمزيد", "📢 {}\n\n💡 لا تفوت الفرصة"
        ]
    
    def disguise_text(self, text):
        result = text
        for keyword, replacements in self.synonyms.items():
            if keyword in result and random.random() > 0.7:
                result = result.replace(keyword, random.choice(replacements))
        return result
    
    def disguise_link(self, text):
        return re.sub(r't\.me', 't\u200B.me', text)
    
    def random_delay(self, base_delay=12):
        return random.randint(int(base_delay * 0.8), int(base_delay * 1.5))
    
    def get_variation(self, text, variation_count=6):
        variations = set()
        for _ in range(variation_count * 2):
            variant = text
            if random.random() > 0.6:
                variant = self.disguise_text(variant)
            if random.random() > 0.7:
                variant = self.disguise_link(variant)
            if random.random() > 0.8:
                variant = random.choice(self.templates).format(variant)
            variations.add(variant)
        return list(variations)[:variation_count]
    
    def add_invisible_chars(self, text):
        if not SETTINGS.get('encryption', True):
            return text
        return advanced_encryption.encrypt_smart(text)
    
    async def send_safe(self, client, chat_id, original_text, group_name=""):
        try:
            variations = self.get_variation(original_text, 6)
            final_text = random.choice(variations)
            final_text = self.add_invisible_chars(final_text)
            await asyncio.sleep(self.random_delay(3))
            await client.send_message(chat_id, final_text)
            self.last_posts[chat_id] = datetime.now()
            return True, "تم النشر بنجاح"
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            return False, f"Flood wait: {e.seconds}s"
        except Exception as e:
            return False, str(e)

anti_detection = AntiDetection()

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

# ==================== قاعدة البيانات ====================

class Database:
    def __init__(self):
        self.db_path = DB_PATH
        self.init_database()
    
    def init_database(self):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP)''')
            c.execute('''CREATE TABLE IF NOT EXISTS messages (msg_id TEXT PRIMARY KEY, content TEXT, created_at TIMESTAMP, is_active INTEGER DEFAULT 0)''')
            c.execute('''CREATE TABLE IF NOT EXISTS accounts (phone TEXT PRIMARY KEY, session_str TEXT, added_at TIMESTAMP, last_active TIMESTAMP, status TEXT, total_posts INTEGER DEFAULT 0, success_posts INTEGER DEFAULT 0, failed_posts INTEGER DEFAULT 0)''')
            c.execute('''CREATE TABLE IF NOT EXISTS groups (group_id TEXT PRIMARY KEY, group_name TEXT, group_username TEXT, group_type TEXT, members_count INTEGER DEFAULT 0, added_by TEXT, added_at TIMESTAMP, last_post TIMESTAMP, post_count INTEGER DEFAULT 0, is_blacklisted INTEGER DEFAULT 0)''')
            c.execute('''CREATE TABLE IF NOT EXISTS posting_history (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, group_id TEXT, group_name TEXT, sent_at TIMESTAMP, status TEXT, error TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS joined_links (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, group_id TEXT, group_name TEXT, joined_at TIMESTAMP, joined_by TEXT)''')
            conn.commit()
            conn.close()
            logger.success("✅ قاعدة البيانات المحلية جاهزة")
            if not self.get_all_messages():
                self.save_message("default", "📢 مرحباً بك!", is_active=True)
    
    def save_setting(self, key, value):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)', (key, json.dumps(value), datetime.now()))
                conn.commit()
            finally:
                conn.close()
    
    def get_setting(self, key, default=None):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            result = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
            return json.loads(result[0]) if result else default
        finally:
            conn.close()
    
    def get_all_settings(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            rows = conn.execute('SELECT key, value FROM settings').fetchall()
            return {key: json.loads(value) for key, value in rows}
        finally:
            conn.close()
    
    def save_message(self, msg_id, content, is_active=False):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                if is_active:
                    conn.execute('UPDATE messages SET is_active = 0')
                conn.execute('INSERT OR REPLACE INTO messages (msg_id, content, created_at, is_active) VALUES (?, ?, ?, ?)', (msg_id, content, datetime.now(), 1 if is_active else 0))
                conn.commit()
            finally:
                conn.close()
    
    def get_all_messages(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT msg_id, content, is_active FROM messages ORDER BY created_at DESC').fetchall()
        finally:
            conn.close()
    
    def get_active_message(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            row = conn.execute('SELECT msg_id, content FROM messages WHERE is_active = 1').fetchone()
            if row:
                return {'id': row[0], 'content': row[1]}
            msgs = self.get_all_messages()
            if msgs:
                self.set_active_message(msgs[0][0])
                return {'id': msgs[0][0], 'content': msgs[0][1]}
            return None
        finally:
            conn.close()
    
    def set_active_message(self, msg_id):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('UPDATE messages SET is_active = 0')
                conn.execute('UPDATE messages SET is_active = 1 WHERE msg_id = ?', (msg_id,))
                conn.commit()
            finally:
                conn.close()
    
    def delete_message(self, msg_id):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('DELETE FROM messages WHERE msg_id = ?', (msg_id,))
                conn.commit()
            finally:
                conn.close()
    
    def add_account(self, phone, session_str):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('INSERT OR REPLACE INTO accounts (phone, session_str, added_at, last_active, status) VALUES (?, ?, ?, ?, ?)', (phone, session_str, datetime.now(), datetime.now(), 'active'))
                conn.commit()
            finally:
                conn.close()
    
    def remove_account(self, phone):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('DELETE FROM accounts WHERE phone = ?', (phone,))
                conn.commit()
            finally:
                conn.close()
    
    def get_accounts(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT phone, status, total_posts, success_posts, failed_posts FROM accounts ORDER BY added_at DESC').fetchall()
        finally:
            conn.close()
    
    def update_account_status(self, phone, status):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('UPDATE accounts SET status = ?, last_active = ? WHERE phone = ?', (status, datetime.now(), phone))
                conn.commit()
            finally:
                conn.close()
    
    def increment_account_posts(self, phone, success=True):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                if success:
                    conn.execute('UPDATE accounts SET total_posts = total_posts + 1, success_posts = success_posts + 1 WHERE phone = ?', (phone,))
                else:
                    conn.execute('UPDATE accounts SET total_posts = total_posts + 1, failed_posts = failed_posts + 1 WHERE phone = ?', (phone,))
                conn.commit()
            finally:
                conn.close()
    
    def add_group(self, group_id, group_name, group_username, group_type, members_count, added_by):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('INSERT OR IGNORE INTO groups (group_id, group_name, group_username, group_type, members_count, added_by, added_at) VALUES (?, ?, ?, ?, ?, ?, ?)', (str(group_id), group_name or "بدون اسم", group_username or "", group_type, members_count or 0, added_by, datetime.now()))
                conn.commit()
            finally:
                conn.close()
    
    def update_group_post(self, group_id):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('UPDATE groups SET post_count = post_count + 1, last_post = ? WHERE group_id = ?', (datetime.now(), str(group_id)))
                conn.commit()
            finally:
                conn.close()
    
    def blacklist_group(self, group_id):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('UPDATE groups SET is_blacklisted = 1 WHERE group_id = ?', (str(group_id),))
                conn.commit()
            finally:
                conn.close()
    
    def whitelist_group(self, group_id):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('UPDATE groups SET is_blacklisted = 0 WHERE group_id = ?', (str(group_id),))
                conn.commit()
            finally:
                conn.close()
    
    def get_all_groups(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT group_id, group_name, members_count, post_count, is_blacklisted, last_post FROM groups ORDER BY post_count DESC').fetchall()
        finally:
            conn.close()
    
    def get_blacklisted_groups(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT group_id, group_name FROM groups WHERE is_blacklisted = 1').fetchall()
        finally:
            conn.close()
    
    def search_groups(self, query):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT group_id, group_name, members_count FROM groups WHERE group_name LIKE ? LIMIT 20', (f'%{query}%',)).fetchall()
        finally:
            conn.close()
    
    def log_post(self, phone, group_id, group_name, status='success', error=None):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('INSERT INTO posting_history (phone, group_id, group_name, sent_at, status, error) VALUES (?, ?, ?, ?, ?, ?)', (phone, str(group_id), group_name[:50], datetime.now(), status, error))
                if status == 'success':
                    self.increment_account_posts(phone, success=True)
                    self.update_group_post(group_id)
                else:
                    self.increment_account_posts(phone, success=False)
                conn.commit()
            finally:
                conn.close()
    
    def get_posting_stats(self, hours=24):
        since = datetime.now() - timedelta(hours=hours)
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            total = conn.execute('SELECT COUNT(*) FROM posting_history WHERE sent_at > ?', (since,)).fetchone()[0]
            success = conn.execute("SELECT COUNT(*) FROM posting_history WHERE sent_at > ? AND status = 'success'", (since,)).fetchone()[0]
            failed = conn.execute("SELECT COUNT(*) FROM posting_history WHERE sent_at > ? AND status = 'failed'", (since,)).fetchone()[0]
            return {'total': total, 'success': success, 'failed': failed}
        finally:
            conn.close()
    
    def get_recent_posts(self, limit=10):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT phone, group_name, status, sent_at FROM posting_history ORDER BY sent_at DESC LIMIT ?', (limit,)).fetchall()
        finally:
            conn.close()
    
    def add_joined_link(self, link, group_id, group_name, joined_by):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('INSERT INTO joined_links (link, group_id, group_name, joined_at, joined_by) VALUES (?, ?, ?, ?, ?)', (link, str(group_id), group_name[:50], datetime.now(), joined_by))
                conn.commit()
            finally:
                conn.close()
    
    def get_joined_links(self, limit=100):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT link, group_name, joined_at, joined_by FROM joined_links ORDER BY joined_at DESC LIMIT ?', (limit,)).fetchall()
        finally:
            conn.close()
    
    def get_joined_links_count(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT COUNT(*) FROM joined_links').fetchone()[0]
        finally:
            conn.close()
    
    def create_backup(self):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"{BACKUPS_DIR}/backup_{timestamp}.db"
        with db_lock:
            shutil.copy2(self.db_path, backup_file)
        backups = sorted(Path(BACKUPS_DIR).glob('backup_*.db'))
        if len(backups) > 20:
            for old in backups[:-20]:
                old.unlink()
        return backup_file

db = Database()

# ==================== المتغيرات العامة ====================

USER_CLIENTS = {}
SETTINGS = {
    'interval': 12,
    'encryption': True,
    'auto_join_enabled': True,
    'save_joined_links': True,
    'anti_detection': True,
    'warm_up_enabled': False
}
SETTINGS.update(db.get_all_settings())
TEMP = {}
is_posting = False
bot = None
start_time = datetime.now()

# ==================== وظائف مساعدة ====================

def format_number(num):
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

# ==================== الأزرار ====================

def main_buttons():
    enc_status = "✅ مفعل" if SETTINGS['encryption'] else "❌ معطل"
    anti_status = "✅ مفعل" if SETTINGS.get('anti_detection', True) else "❌ معطل"
    active_msg = db.get_active_message()
    msg_preview = active_msg['content'][:20] + "..." if active_msg and len(active_msg['content']) > 20 else (active_msg['content'][:20] if active_msg else "لا يوجد")
    
    return [
        [Button.inline("➕ إضافة حساب", b"add"), Button.inline("🗑 حذف حساب", b"del_list")],
        [Button.inline("📝 إدارة الرسائل", b"manage_messages"), Button.inline("⏱ ضبط الوقت", b"time")],
        [Button.inline(f"📨 {msg_preview}", b"show_active")],
        [Button.inline("🚀 بدء النشر", b"start_p"), Button.inline("🛑 إيقاف النشر", b"stop_p")],
        [Button.inline(f"🛡 التشفير: {enc_status}", b"toggle_enc"), Button.inline("📊 الحالة", b"status")],
        [Button.inline(f"🎭 مكافحة الكشف: {anti_status}", b"toggle_anti")],
        [Button.inline("📢 المجموعات", b"view_chats"), Button.inline("⚙️ إعدادات متقدمة", b"advanced")],
        [Button.inline("📈 إحصائيات", b"stats"), Button.inline("🔗 الروابط", b"view_joined_links")],
        [Button.inline("📊 تقارير", b"real_reports")]
    ]

def messages_buttons():
    return [
        [Button.inline("📋 عرض الكل", b"list_messages")],
        [Button.inline("➕ إضافة جديدة", b"add_message")],
        [Button.inline("✅ تعيين نشطة", b"set_active_message")],
        [Button.inline("🗑 حذف رسالة", b"delete_message")],
        [Button.inline("⬅️ عودة", b"back")]
    ]

def advanced_buttons():
    auto_join = "✅" if SETTINGS.get('auto_join_enabled', True) else "❌"
    save_links = "✅" if SETTINGS.get('save_joined_links', True) else "❌"
    anti_detect = "✅" if SETTINGS.get('anti_detection', True) else "❌"
    warm_up = "✅" if SETTINGS.get('warm_up_enabled', True) else "❌"
    
    return [
        [Button.inline(f"🤖 انضمام تلقائي {auto_join}", b"toggle_autojoin")],
        [Button.inline(f"💾 حفظ الروابط {save_links}", b"toggle_save_links")],
        [Button.inline(f"🎭 مكافحة الكشف {anti_detect}", b"toggle_anti")],
        [Button.inline(f"🔥 تسخين المجموعات {warm_up}", b"toggle_warmup")],
        [Button.inline("🗑️ حذف قاعدة البيانات", b"delete_database")],
        [Button.inline(f"🚫 محظورات: {group_blacklist.get_banned_count()}", b"view_temp_blacklist")],
        [Button.inline("🚫 إدارة المحظورات", b"blacklist_menu")],
        [Button.inline("🗂 إدارة المجموعات", b"manage_groups")],
        [Button.inline("📊 إحصائيات تفصيلية", b"detailed_stats")],
        [Button.inline("💾 نسخ احتياطي", b"backup")],
        [Button.inline("⬅️ عودة", b"back")]
    ]

def blacklist_buttons():
    return [
        [Button.inline("➕ إضافة للمحظورات", b"add_blacklist")],
        [Button.inline("➖ إزالة من المحظورات", b"remove_blacklist")],
        [Button.inline("📋 عرض المحظورات", b"view_blacklist")],
        [Button.inline("⬅️ عودة", b"advanced")]
    ]

def groups_buttons():
    return [
        [Button.inline("🔄 تحديث المجموعات", b"refresh_groups")],
        [Button.inline("🔍 بحث في المجموعات", b"search_groups")],
        [Button.inline("📊 إحصائيات المجموعات", b"group_stats")],
        [Button.inline("⬅️ عودة", b"advanced")]
    ]

def reports_buttons():
    return [
        [Button.inline("📊 إحصائيات النشر", b"real_stats")],
        [Button.inline("👥 تقرير الحسابات", b"accounts_report")],
        [Button.inline("📢 تقرير المجموعات", b"groups_report")],
        [Button.inline("🔗 تقرير الروابط", b"links_report")],
        [Button.inline("📋 سجل النشر", b"posting_history")],
        [Button.inline("⬅️ عودة", b"back")]
    ]

# ==================== المعالجات ====================

async def start_handler(event):
    if event.sender_id != ADMIN_ID:
        return
    accounts = db.get_accounts()
    groups = db.get_all_groups()
    joined_links = db.get_joined_links_count()
    active_msg = db.get_active_message()
    
    await event.respond(
        f"👋 **أهلاً بك في بوت النشر الخارق!**\n\n"
        f"📊 **الإحصائيات:**\n"
        f"• الحسابات: {len(accounts)}\n"
        f"• المجموعات: {len(groups)}\n"
        f"• المحظورات: {len(db.get_blacklisted_groups())}\n"
        f"• الروابط المنضم لها: {joined_links}\n"
        f"• الرسائل المحفوظة: {len(db.get_all_messages())}\n\n"
        f"🛡 **مكافحة الكشف:** {'مفعلة' if SETTINGS.get('anti_detection', True) else 'معطلة'}\n"
        f"🐢 **انضمام بطيء:** مفعل (رابط واحد كل 2-4 دقائق)\n\n"
        f"📨 **الرسالة النشطة:**\n{active_msg['content'][:100] if active_msg else 'لا توجد'}\n\n"
        f"استخدم الأزرار للتحكم:", 
        buttons=main_buttons()
    )

async def callback_handler(event):
    global SETTINGS
    global is_posting
    
    if event.sender_id != ADMIN_ID:
        return
    
    data = event.data.decode()
    logger.info(f"🖱 نقرة: {data}")
    
    if data == "status":
        await show_status(event)
    elif data == "stats":
        await show_stats(event)
    elif data == "add":
        await event.edit("📱 أرسل رقم الهاتف مع رمز الدولة (مثال: +967...)"); 
        TEMP[ADMIN_ID] = "phone"
    elif data == "del_list":
        await show_delete_list(event)
    elif data.startswith("rm_"):
        await delete_account(event, data.replace("rm_", ""))
    elif data == "time":
        await event.edit("⏱ أرسل الفاصل الزمني (10-120 ثانية):"); 
        TEMP[ADMIN_ID] = "time"
    elif data == "toggle_enc":
        SETTINGS['encryption'] = not SETTINGS['encryption']
        db.save_setting('encryption', SETTINGS['encryption'])
        await event.answer(f"✅ التشفير {'مفعل' if SETTINGS['encryption'] else 'معطل'}")
        await event.edit("👋 لوحة التحكم:", buttons=main_buttons())
    elif data == "toggle_anti":
        SETTINGS['anti_detection'] = not SETTINGS.get('anti_detection', True)
        db.save_setting('anti_detection', SETTINGS['anti_detection'])
        await event.answer(f"✅ مكافحة الكشف {'مفعلة' if SETTINGS['anti_detection'] else 'معطلة'}")
        await event.edit("👋 لوحة التحكم:", buttons=main_buttons())
    elif data == "toggle_warmup":
        SETTINGS['warm_up_enabled'] = not SETTINGS.get('warm_up_enabled', True)
        db.save_setting('warm_up_enabled', SETTINGS['warm_up_enabled'])
        await event.answer(f"✅ تسخين المجموعات {'مفعل' if SETTINGS['warm_up_enabled'] else 'معطل'}")
        await event.edit("⚙️ الإعدادات المتقدمة:", buttons=advanced_buttons())
    elif data == "view_chats":
        await show_groups(event)
    elif data == "advanced":
        await event.edit("⚙️ الإعدادات المتقدمة", buttons=advanced_buttons())
    elif data == "restart":
        await event.edit("🔄 جاري إعادة التشغيل...")
        await asyncio.sleep(2)
        os.execl(sys.executable, sys.executable, *sys.argv)
    elif data == "back":
        await event.edit("👋 لوحة التحكم الرئيسية", buttons=main_buttons())
    elif data == "backup":
        await create_backup_handler(event)
    elif data == "show_active":
        active = db.get_active_message()
        if active:
            await event.answer(f"الرسالة النشطة: {active['content'][:50]}...", alert=True)
        else:
            await event.answer("❌ لا توجد رسالة نشطة", alert=True)
    
    elif data == "delete_database":
        await event.edit(
            "⚠️ **تحذير!** ⚠️\n\n"
            "أنت على وشك حذف قاعدة البيانات بالكامل!\n"
            "سيتم حذف:\n"
            "• جميع الحسابات المحفوظة\n"
            "• جميع الرسائل\n"
            "• سجل النشر\n"
            "• المجموعات المحفوظة\n"
            "• الروابط المنضم لها\n\n"
            "**هل أنت متأكد؟**",
            buttons=[
                [Button.inline("✅ نعم، احذف كل شيء", b"confirm_delete_db")],
                [Button.inline("❌ إلغاء", b"advanced")]
            ]
        )
    
    elif data == "confirm_delete_db":
        try:
            backup_file = db.create_backup()
            logger.info(f"📦 تم إنشاء نسخة احتياطية: {backup_file}")
            
            for phone, client in USER_CLIENTS.items():
                try:
                    await client.disconnect()
                except:
                    pass
            USER_CLIENTS.clear()
            
            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
            
            db.init_database()
            
            SETTINGS.update({
                'interval': 12,
                'encryption': True,
                'auto_join_enabled': True,
                'save_joined_links': True,
                'anti_detection': True,
                'warm_up_enabled': False
            })
            
            await event.edit(
                "✅ **تم حذف قاعدة البيانات بنجاح!**\n\n"
                "• تم إنشاء نسخة احتياطية\n"
                "• تم إعادة تهيئة قاعدة البيانات\n"
                "• جميع الحسابات تم حذفها\n\n"
                "اضغط /start للبدء من جديد",
                buttons=[[Button.inline("🔄 العودة للقائمة", b"back")]]
            )
        except Exception as e:
            await event.edit(f"❌ فشل الحذف: {str(e)[:100]}", buttons=[[Button.inline("⬅️ عودة", b"advanced")]])
    
    elif data == "view_temp_blacklist":
        banned = group_blacklist.banned_groups
        if not banned:
            await event.answer("📭 لا توجد مجموعات محظورة مؤقتاً", alert=True)
        else:
            text = "🚫 **المجموعات المحظورة مؤقتاً:**\n\n"
            for gid in list(banned)[:20]:
                text += f"• {gid}\n"
            await event.edit(text, buttons=advanced_buttons())
    
    elif data == "manage_messages":
        await event.edit("📝 **إدارة الرسائل**", buttons=messages_buttons())
    elif data == "list_messages":
        await list_all_messages(event)
    elif data == "add_message":
        await event.edit("📝 **أرسل نص الرسالة الجديدة:**")
        TEMP[ADMIN_ID] = "new_message"
    elif data == "set_active_message":
        await show_set_active_message(event)
    elif data.startswith("set_active_"):
        msg_id = data.replace("set_active_", "")
        db.set_active_message(msg_id)
        await event.answer("✅ تم تعيين الرسالة كنشطة", alert=True)
        await event.edit("📝 إدارة الرسائل", buttons=messages_buttons())
    elif data == "delete_message":
        await show_delete_message(event)
    elif data.startswith("del_msg_"):
        msg_id = data.replace("del_msg_", "")
        db.delete_message(msg_id)
        await event.answer("✅ تم حذف الرسالة", alert=True)
        await event.edit("📝 إدارة الرسائل", buttons=messages_buttons())
    
    elif data == "toggle_autojoin":
        SETTINGS['auto_join_enabled'] = not SETTINGS.get('auto_join_enabled', True)
        db.save_setting('auto_join_enabled', SETTINGS['auto_join_enabled'])
        await event.answer(f"✅ الانضمام التلقائي {'مفعل' if SETTINGS['auto_join_enabled'] else 'معطل'}")
        await event.edit("⚙️ الإعدادات المتقدمة:", buttons=advanced_buttons())
    elif data == "toggle_save_links":
        SETTINGS['save_joined_links'] = not SETTINGS.get('save_joined_links', True)
        db.save_setting('save_joined_links', SETTINGS['save_joined_links'])
        await event.answer(f"✅ حفظ الروابط {'مفعل' if SETTINGS['save_joined_links'] else 'معطل'}")
        await event.edit("⚙️ الإعدادات المتقدمة:", buttons=advanced_buttons())
    elif data == "view_joined_links":
        await show_joined_links(event)
    elif data == "blacklist_menu":
        await event.edit("🚫 قائمة المحظورات", buttons=blacklist_buttons())
    elif data == "manage_groups":
        await event.edit("🗂 إدارة المجموعات", buttons=groups_buttons())
    elif data == "detailed_stats":
        await show_detailed_stats(event)
    elif data == "posting_history":
        await show_posting_history(event)
    elif data == "view_blacklist":
        await show_blacklist(event)
    elif data == "add_blacklist":
        await event.edit("🚫 أرسل اسم المجموعة أو معرفها لحظرها:")
        TEMP[ADMIN_ID] = "add_blacklist"
    elif data == "remove_blacklist":
        await show_remove_blacklist(event)
    elif data.startswith("unblack_"):
        await remove_from_blacklist(event, data.replace("unblack_", ""))
    elif data == "refresh_groups":
        await refresh_groups(event)
    elif data == "search_groups":
        await event.edit("🔍 أرسل كلمة البحث:")
        TEMP[ADMIN_ID] = "search_groups"
    elif data == "group_stats":
        await show_group_stats(event)
    
    elif data == "real_reports":
        await event.edit("📊 **التقارير**", buttons=reports_buttons())
    elif data == "real_stats":
        await show_real_stats(event)
    elif data == "accounts_report":
        await show_accounts_report(event)
    elif data == "groups_report":
        await show_groups_report(event)
    elif data == "links_report":
        await show_links_report(event)
    
    elif data == "start_p":
        if not USER_CLIENTS:
            return await event.answer("❌ لا توجد حسابات!", alert=True)
        active_msg = db.get_active_message()
        if not active_msg:
            return await event.answer("❌ لا توجد رسالة نشطة!", alert=True)
        is_posting = True
        asyncio.create_task(poster())
        await event.edit("🚀 بدأ النشر", buttons=main_buttons())
    elif data == "stop_p":
        is_posting = False
        await event.edit("🛑 تم إيقاف النشر", buttons=main_buttons())

# ===== دوال العرض =====

async def list_all_messages(event):
    messages = db.get_all_messages()
    if not messages:
        await event.edit("📭 لا توجد رسائل", buttons=messages_buttons())
        return
    
    text = "📋 **جميع الرسائل المحفوظة**\n\n"
    for i, (msg_id, content, is_active) in enumerate(messages[:15], 1):
        status = "🌟 نشطة" if is_active else "📄 عادية"
        preview = content[:50] + "..." if len(content) > 50 else content
        text += f"{i}. {status}\n   `{preview}`\n   🆔 {msg_id}\n\n"
    
    if len(messages) > 15:
        text += f"\n... و {len(messages) - 15} رسالة أخرى"
    
    await event.edit(text, buttons=messages_buttons())

async def show_set_active_message(event):
    messages = db.get_all_messages()
    if not messages:
        await event.answer("❌ لا توجد رسائل!", alert=True)
        return
    
    btns = []
    for msg_id, content, is_active in messages[:10]:
        preview = content[:25] + "..." if len(content) > 25 else content
        status = "🌟" if is_active else "📄"
        btns.append([Button.inline(f"{status} {preview}", f"set_active_{msg_id}".encode())])
    btns.append([Button.inline("⬅️ عودة", b"manage_messages")])
    await event.edit("✅ اختر الرسالة النشطة", buttons=btns)

async def show_delete_message(event):
    messages = db.get_all_messages()
    if not messages:
        await event.answer("❌ لا توجد رسائل!", alert=True)
        return
    
    btns = []
    for msg_id, content, is_active in messages[:10]:
        preview = content[:25] + "..." if len(content) > 25 else content
        status = "🌟" if is_active else "📄"
        btns.append([Button.inline(f"🗑 {status} {preview}", f"del_msg_{msg_id}".encode())])
    btns.append([Button.inline("⬅️ عودة", b"manage_messages")])
    await event.edit("🗑 اختر رسالة للحذف", buttons=btns)

async def show_real_stats(event):
    stats_24h = db.get_posting_stats(24)
    stats_7d = db.get_posting_stats(168)
    recent = db.get_recent_posts(10)
    
    text = "📊 **إحصائيات النشر**\n\n"
    text += f"**آخر 24 ساعة:**\n"
    text += f"• الإجمالي: {stats_24h['total']}\n"
    text += f"• الناجح: {stats_24h['success']}\n"
    text += f"• الفاشل: {stats_24h['failed']}\n"
    text += f"• نسبة النجاح: {stats_24h['success']/(stats_24h['total'] or 1)*100:.1f}%\n\n"
    
    text += f"**آخر 7 أيام:**\n"
    text += f"• الإجمالي: {stats_7d['total']}\n"
    text += f"• الناجح: {stats_7d['success']}\n"
    text += f"• الفاشل: {stats_7d['failed']}\n"
    text += f"• نسبة النجاح: {stats_7d['success']/(stats_7d['total'] or 1)*100:.1f}%\n\n"
    
    text += f"**آخر 10 عمليات:**\n"
    for phone, group, status, sent_at in recent:
        time_str = datetime.fromisoformat(sent_at).strftime('%H:%M:%S')
        icon = "✅" if status == 'success' else "❌"
        text += f"{icon} {time_str} - {group[:25]} ({phone[-8:]})\n"
    
    await event.edit(text, buttons=reports_buttons())

async def show_accounts_report(event):
    accounts = db.get_accounts()
    if not accounts:
        await event.edit("📭 لا توجد حسابات", buttons=reports_buttons())
        return
    
    text = "👥 **تقرير الحسابات**\n\n"
    total_posts = 0
    total_success = 0
    
    for phone, status, total, success, failed in accounts:
        rate = (success / total * 100) if total > 0 else 0
        total_posts += total
        total_success += success
        status_icon = "🟢" if status == 'active' else "🔴"
        text += f"{status_icon} `{phone[-12:]}`\n"
        text += f"   📊 {total} | ✅ {success} | ❌ {failed} | 📈 {rate:.1f}%\n\n"
    
    text += f"\n**الإجمالي:**\n"
    text += f"• الحسابات: {len(accounts)}\n"
    text += f"• إجمالي المنشورات: {total_posts}\n"
    text += f"• الناجح: {total_success}\n"
    text += f"• نسبة النجاح: {total_success/(total_posts or 1)*100:.1f}%"
    
    await event.edit(text, buttons=reports_buttons())

async def show_groups_report(event):
    groups = db.get_all_groups()
    if not groups:
        await event.edit("📭 لا توجد مجموعات", buttons=reports_buttons())
        return
    
    text = "📢 **تقرير المجموعات**\n\n"
    total_members = 0
    total_posts = 0
    
    top_groups = sorted(groups, key=lambda x: x[3], reverse=True)[:10]
    
    for gid, name, members, posts, bl, last in top_groups:
        total_members += members or 0
        total_posts += posts
        status = "🚫" if bl else "✅"
        members_fmt = format_number(members) if members else "?"
        text += f"{status} **{name[:30]}**\n"
        text += f"   👥 {members_fmt} | 📨 {posts}\n\n"
    
    text += f"**الإجمالي:**\n"
    text += f"• المجموعات: {len(groups)}\n"
    text += f"• إجمالي الأعضاء: {format_number(total_members)}\n"
    text += f"• إجمالي المنشورات: {total_posts}\n"
    text += f"• المتوسط: {total_posts/len(groups):.1f}"
    
    await event.edit(text, buttons=reports_buttons())

async def show_links_report(event):
    links = db.get_joined_links(50)
    if not links:
        await event.edit("📭 لا توجد روابط", buttons=reports_buttons())
        return
    
    text = "🔗 **تقرير الروابط**\n\n"
    text += f"📊 إجمالي الروابط: {len(links)}\n\n"
    text += "**آخر 20 رابط:**\n"
    
    for link, group_name, joined_at, joined_by in links[:20]:
        time_str = datetime.fromisoformat(joined_at).strftime('%Y-%m-%d %H:%M')
        text += f"• **{group_name[:30]}**\n"
        text += f"  🔗 {link[:40]}...\n"
        text += f"  📱 {joined_by[-8:]} | 🕐 {time_str}\n\n"
    
    await event.edit(text, buttons=reports_buttons())

async def show_status(event):
    accounts = db.get_accounts()
    groups = db.get_all_groups()
    blacklisted = db.get_blacklisted_groups()
    stats = db.get_posting_stats()
    joined_links = db.get_joined_links_count()
    messages_count = len(db.get_all_messages())
    active_msg = db.get_active_message()
    uptime = datetime.now() - start_time
    hours = uptime.total_seconds() // 3600
    minutes = (uptime.total_seconds() % 3600) // 60
    
    active_accounts = len([a for a in accounts if a[1] == 'active'])
    
    text = f"📊 **حالة البوت**\n\n"
    text += f"⏰ **وقت التشغيل:** {int(hours)} س {int(minutes)} د\n"
    text += f"👤 **الحسابات:** {active_accounts}/{len(accounts)}\n"
    text += f"📨 **المنشورات اليوم:** {stats['total']}\n"
    text += f"✅ **الناجح:** {stats['success']}\n"
    text += f"❌ **الفاشل:** {stats['failed']}\n"
    text += f"📢 **المجموعات:** {len(groups)}\n"
    text += f"🚫 **المحظورات:** {len(blacklisted)}\n"
    text += f"🔗 **الروابط:** {joined_links}\n"
    text += f"📝 **الرسائل:** {messages_count}\n"
    text += f"⚙️ **الفاصل:** {SETTINGS['interval']} ثانية\n"
    text += f"🎭 **مكافحة الكشف:** {'🟢 مفعلة' if SETTINGS.get('anti_detection', True) else '🔴 معطلة'}\n"
    text += f"🐢 **انضمام بطيء:** مفعل (رابط واحد كل 2-4 دقائق)\n"
    text += f"🔄 **النشر:** {'🟢 نشط' if is_posting else '🔴 متوقف'}\n"
    
    if active_msg:
        text += f"\n📨 **الرسالة النشطة:**\n{active_msg['content'][:100]}..."
    
    await event.edit(text, buttons=main_buttons())

async def show_stats(event):
    stats = db.get_posting_stats()
    recent = db.get_recent_posts(5)
    
    text = f"📈 **إحصائيات آخر 24 ساعة**\n\n"
    text += f"📊 الإجمالي: {stats['total']}\n"
    text += f"✅ الناجح: {stats['success']}\n"
    text += f"❌ الفاشل: {stats['failed']}\n"
    text += f"📊 نسبة النجاح: {stats['success']/(stats['total'] or 1)*100:.1f}%\n\n"
    text += f"📋 آخر النشاطات:\n"
    
    for phone, group, status, sent_at in recent:
        time_str = datetime.fromisoformat(sent_at).strftime('%H:%M')
        icon = "✅" if status == 'success' else "❌"
        text += f"{icon} {time_str} - {group[:20]}\n"
    
    await event.edit(text, buttons=main_buttons())

async def show_detailed_stats(event):
    accounts = db.get_accounts()
    groups = db.get_all_groups()
    joined_links = db.get_joined_links_count()
    
    text = "📊 **إحصائيات تفصيلية**\n\n"
    text += "**أفضل الحسابات:**\n"
    
    sorted_accounts = sorted(accounts, key=lambda x: x[2], reverse=True)[:5]
    for phone, status, posts, success, failed in sorted_accounts:
        rate = (success / posts * 100) if posts > 0 else 0
        text += f"• {phone[-8:]}: {posts} منشور ({rate:.1f}%)\n"
    
    text += "\n**أفضل المجموعات:**\n"
    sorted_groups = sorted(groups, key=lambda x: x[3], reverse=True)[:5]
    for gid, name, members, posts, bl, last in sorted_groups:
        text += f"• {name[:20]}: {posts} منشور\n"
    
    text += f"\n🔗 **إحصائيات الروابط:**\n"
    text += f"• إجمالي الروابط: {joined_links}"
    
    await event.edit(text, buttons=advanced_buttons())

async def show_posting_history(event):
    recent = db.get_recent_posts(15)
    text = "📋 **آخر 15 عملية نشر**\n\n"
    
    for phone, group, status, sent_at in recent:
        time_str = datetime.fromisoformat(sent_at).strftime('%H:%M:%S')
        icon = "✅" if status == 'success' else "❌"
        text += f"{icon} {time_str} - {group[:20]}\n"
    
    await event.edit(text, buttons=advanced_buttons())

async def show_delete_list(event):
    accounts = db.get_accounts()
    if not accounts:
        return await event.answer("❌ لا توجد حسابات", alert=True)
    
    btns = []
    for phone, status, posts, success, failed in accounts[:10]:
        short = phone[-8:] if len(phone) > 8 else phone
        status_icon = "🟢" if status == 'active' else "🔴"
        btns.append([Button.inline(f"{status_icon} {short} ({posts})", f"rm_{phone}".encode())])
    
    btns.append([Button.inline("⬅️ عودة", b"back")])
    await event.edit("🗑 اختر حساباً للحذف", buttons=btns)

async def show_groups(event):
    groups = db.get_all_groups()
    blacklisted = db.get_blacklisted_groups()
    
    text = f"📢 **المجموعات**\nالإجمالي: {len(groups)}\nالمحظور: {len(blacklisted)}\n\n"
    
    for gid, name, members, posts, bl, last in groups[:15]:
        name_short = name[:25] if name else "بدون اسم"
        status = "🚫" if bl else "✅"
        members_fmt = format_number(members) if members else "?"
        text += f"{status} {name_short}\n   👥 {members_fmt} | 📨 {posts}\n"
    
    if len(groups) > 15:
        text += f"\n... و {len(groups) - 15} مجموعة أخرى"
    
    await event.edit(text, buttons=main_buttons())

async def show_blacklist(event):
    blacklisted = db.get_blacklisted_groups()
    if not blacklisted:
        await event.edit("📭 لا توجد مجموعات محظورة", buttons=blacklist_buttons())
        return
    
    text = "🚫 **المجموعات المحظورة**\n\n"
    for gid, name in blacklisted[:20]:
        text += f"• {name[:40]}\n"
    
    if len(blacklisted) > 20:
        text += f"\n... و {len(blacklisted) - 20} مجموعة أخرى"
    
    await event.edit(text, buttons=blacklist_buttons())

async def show_remove_blacklist(event):
    blacklisted = db.get_blacklisted_groups()
    if not blacklisted:
        return await event.answer("❌ لا توجد محظورات", alert=True)
    
    btns = []
    for gid, name in blacklisted[:10]:
        btns.append([Button.inline(f"✅ {name[:20]}", f"unblack_{gid}".encode())])
    
    btns.append([Button.inline("⬅️ عودة", b"blacklist_menu")])
    await event.edit("✅ اختر مجموعة للإزالة", buttons=btns)

async def show_group_stats(event):
    groups = db.get_all_groups()
    if not groups:
        return await event.answer("❌ لا توجد مجموعات", alert=True)
    
    most_active = sorted(groups, key=lambda x: x[3], reverse=True)[:5]
    largest = sorted(groups, key=lambda x: x[2] or 0, reverse=True)[:5]
    
    text = "📊 **إحصائيات المجموعات**\n\n"
    text += "**الأكثر نشاطاً:**\n"
    for gid, name, members, posts, bl, last in most_active:
        text += f"• {name[:25]}: {posts} منشور\n"
    
    text += "\n**الأكبر عدداً:**\n"
    for gid, name, members, posts, bl, last in largest:
        members_fmt = format_number(members) if members else "?"
        text += f"• {name[:25]}: {members_fmt} عضو\n"
    
    await event.edit(text, buttons=groups_buttons())

async def show_joined_links(event):
    links = db.get_joined_links(20)
    if not links:
        await event.edit("📭 لا توجد روابط\n\nأرسل روابط المجموعات للانضمام (رابط واحد فقط لكل رسالة)", buttons=main_buttons())
        return
    
    text = "🔗 **آخر 20 رابط تم الانضمام لها**\n\n"
    for link, group_name, joined_at, joined_by in links:
        time_str = datetime.fromisoformat(joined_at).strftime('%Y-%m-%d %H:%M')
        text += f"• **{group_name[:30]}**\n"
        text += f"  🔗 {link[:40]}...\n"
        text += f"  📱 {joined_by[-8:]} | 🕐 {time_str}\n\n"
    
    await event.edit(text, buttons=main_buttons())

# ===== دوال الإجراءات =====

async def delete_account(event, phone):
    if phone in USER_CLIENTS:
        await USER_CLIENTS[phone].disconnect()
        del USER_CLIENTS[phone]
    db.remove_account(phone)
    await event.answer(f"✅ تم حذف {phone}", alert=True)
    await show_delete_list(event)

async def remove_from_blacklist(event, group_id):
    db.whitelist_group(group_id)
    group_blacklist.clear_banned(str(group_id))
    await event.answer("✅ تمت الإزالة", alert=True)
    await show_blacklist(event)

async def refresh_groups(event):
    await event.answer("🔄 جاري تحديث المجموعات...")
    count = 0
    for phone, client in USER_CLIENTS.items():
        try:
            async for dialog in client.iter_dialogs():
                if dialog.is_group:
                    members = getattr(dialog.entity, 'participants_count', 0)
                    db.add_group(dialog.id, dialog.name, getattr(dialog.entity, 'username', None), 'group', members, phone)
                    count += 1
        except:
            pass
    await event.answer(f"✅ تم تحديث {count} مجموعة")
    await event.edit("🗂 إدارة المجموعات:", buttons=groups_buttons())

async def create_backup_handler(event):
    try:
        backup_file = db.create_backup()
        await event.answer(f"✅ تم إنشاء النسخة", alert=True)
    except Exception as e:
        await event.answer(f"❌ فشل النسخ: {e}", alert=True)

async def refresh_groups_async():
    count = 0
    for phone, client in USER_CLIENTS.items():
        try:
            async for dialog in client.iter_dialogs():
                if dialog.is_group:
                    members = getattr(dialog.entity, 'participants_count', 0)
                    db.add_group(dialog.id, dialog.name, getattr(dialog.entity, 'username', None), 'group', members, phone)
                    count += 1
        except:
            pass
    logger.info(f"✅ تم تحديث {count} مجموعة")

# ===== معالج النصوص والانضمام البطيء =====

async def text_handler(event):
    state = TEMP.get(ADMIN_ID)
    text = event.message.text.strip()
    
    if state == "new_message":
        msg_id = f"msg_{int(time.time())}"
        db.save_message(msg_id, text, is_active=False)
        TEMP.pop(ADMIN_ID)
        await event.respond(f"✅ **تم إضافة الرسالة!**\n\n📝 {text[:100]}...\n🆔 {msg_id}", buttons=messages_buttons())
        return
    
    elif state == "phone":
        await handle_phone_login(event, text)
    
    elif state == "time":
        try:
            interval = int(text)
            if 10 <= interval <= 120:
                SETTINGS['interval'] = interval
                db.save_setting('interval', interval)
                TEMP.pop(ADMIN_ID)
                await event.respond(f"✅ تم ضبط الوقت على {text} ثانية", buttons=main_buttons())
            else:
                await event.respond("❌ الرجاء إدخال قيمة بين 10 و 120")
        except:
            await event.respond("❌ أرسل رقماً فقط")
    
    elif state == "add_blacklist":
        groups = db.search_groups(text)
        if groups:
            for gid, name, members in groups[:5]:
                db.blacklist_group(gid)
            await event.respond(f"✅ تم حظر {len(groups[:5])} مجموعة")
        else:
            await event.respond("❌ لم يتم العثور على مجموعات")
        TEMP.pop(ADMIN_ID)
        await event.respond("⚙️ الإعدادات المتقدمة:", buttons=advanced_buttons())
    
    elif state == "search_groups":
        groups = db.search_groups(text)
        if groups:
            msg = f"🔍 **نتائج البحث:**\n\n"
            for gid, name, members in groups:
                msg += f"• {name[:40]}\n  👥 {format_number(members)}\n"
            await event.respond(msg)
        else:
            await event.respond("❌ لا توجد نتائج")
        TEMP.pop(ADMIN_ID)
    
    else:
        links = re.findall(r"(https?://t\.me/(?:joinchat/|\+)[a-zA-Z0-9_-]+|https?://t\.me/[a-zA-Z0-9_]+)", text)
        if links and SETTINGS.get('auto_join_enabled', True) and USER_CLIENTS:
            await handle_auto_join_super_slow(event, links)

async def handle_auto_join_super_slow(event, links):
    max_links = 1
    await event.respond(
        f"🐢 **انضمام بطيء جداً (أقصى حماية)**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 سيتم معالجة رابط واحد فقط\n"
        f"⏱ الوقت المتوقع: 2-4 دقائق\n"
        f"🛡 هذا الإعداد يحمي الحسابات من الحظر\n\n"
        f"جاري البدء..."
    )
    
    success = 0
    failed = 0
    saved = 0
    link = links[0]
    
    initial_delay = random.randint(60, 120)
    logger.info(f"⏸ انتظار {initial_delay} ثانية قبل البدء...")
    await asyncio.sleep(initial_delay)
    
    joined = False
    for phone, client in USER_CLIENTS.items():
        if joined:
            break
            
        try:
            pre_join_delay = random.randint(45, 90)
            logger.info(f"⏸ انتظار {pre_join_delay} ثانية قبل محاولة {phone[-8:]}...")
            await asyncio.sleep(pre_join_delay)
            
            group_info = None
            if "joinchat" in link or "+" in link:
                hash_part = link.split('/')[-1].replace('+', '')
                logger.info(f"🔗 محاولة الانضمام عبر رابط دعوة...")
                updates = await client(ImportChatInviteRequest(hash_part))
                if updates.chats:
                    chat = updates.chats[0]
                    group_info = (chat.id, chat.title)
            else:
                username = link.split('/')[-1]
                logger.info(f"🔗 محاولة الانضمام إلى @{username}...")
                entity = await client.get_entity(username)
                if entity:
                    await client(JoinChannelRequest(link))
                    group_info = (entity.id, getattr(entity, 'title', username))
            
            success += 1
            joined = True
            logger.success(f"✅ تم الانضمام بنجاح باستخدام {phone[-8:]}")
            
            post_join_delay = random.randint(60, 120)
            logger.info(f"⏸ انتظار {post_join_delay} ثانية بعد الانضمام...")
            await asyncio.sleep(post_join_delay)
            
            if SETTINGS.get('save_joined_links', True) and group_info:
                group_id, group_name = group_info
                db.add_joined_link(link, group_id, group_name[:50], phone)
                saved += 1
                logger.success(f"💾 تم حفظ {group_name[:30]} في قاعدة البيانات")
            
            break
            
        except FloodWaitError as e:
            wait_time = e.seconds + random.randint(45, 90)
            logger.warning(f"⏳ FloodWait: انتظار {wait_time} ثانية...")
            await asyncio.sleep(wait_time)
            continue
            
        except Exception as e:
            failed += 1
            logger.error(f"❌ فشل انضمام {phone} إلى {link}: {e}")
            error_delay = random.randint(90, 180)
            logger.info(f"⏸ انتظار {error_delay} ثانية بعد الفشل...")
            await asyncio.sleep(error_delay)
            continue
    
    if not joined:
        failed += 1
        logger.warning(f"⚠️ فشل الانضمام لـ {link} بجميع الحسابات")
        await asyncio.sleep(random.randint(120, 180))
    
    await asyncio.sleep(random.randint(15, 30))
    
    result_text = f"📊 **نتيجة الانضمام البطيء جداً:**\n"
    result_text += f"━━━━━━━━━━━━━━━━━━━━\n"
    result_text += f"✅ نجاح: {success}\n"
    result_text += f"❌ فشل: {failed}\n"
    result_text += f"⏱ تم الانضمام بسرعة بطيئة جداً\n"
    result_text += f"🛡 الحسابات محمية بالكامل"
    if saved > 0:
        result_text += f"\n💾 تم حفظ: {saved} رابط"
    
    await event.respond(result_text)

# دوال تسجيل الدخول
async def handle_phone_login(event, phone):
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        await client.send_code_request(phone)
        TEMP[ADMIN_ID] = {"s": "code", "p": phone, "c": client}
        await event.respond(f"📩 أرسل الكود لـ {phone}:")
    except Exception as e:
        await event.respond(f"❌ خطأ: {str(e)[:100]}")

async def handle_code_verification(event, state, code):
    try:
        client = state["c"]
        phone = state["p"]
        await client.sign_in(phone, code)
        USER_CLIENTS[phone] = client
        db.add_account(phone, client.session.save())
        await event.respond(f"✅ تم تفعيل الحساب {phone}!")
        TEMP.pop(ADMIN_ID)
        asyncio.create_task(refresh_groups_async())
    except SessionPasswordNeededError:
        TEMP[ADMIN_ID]["s"] = "pass"
        await event.respond("🔐 أرسل كلمة المرور:")
    except Exception as e:
        await event.respond(f"❌ فشل: {str(e)[:100]}")

async def handle_password(event, state, password):
    try:
        await state["c"].sign_in(password=password)
        USER_CLIENTS[state["p"]] = state["c"]
        db.add_account(state["p"], state["c"].session.save())
        await event.respond(f"✅ تم التفعيل بنجاح!")
        TEMP.pop(ADMIN_ID)
        asyncio.create_task(refresh_groups_async())
    except Exception as e:
        await event.respond(f"❌ خطأ: {str(e)[:100]}")

# ===== دالة النشر =====
async def poster():
    global is_posting
    logger.info("🚀 بدء النشر بنظام مكافحة الكشف...")
    
    stats = {'total': 0, 'success': 0, 'failed': 0}
    
    while is_posting:
        try:
            if not USER_CLIENTS:
                await asyncio.sleep(10)
                continue
            
            active_msg = db.get_active_message()
            if not active_msg:
                logger.warning("⚠️ لا توجد رسالة نشطة")
                await asyncio.sleep(5)
                continue
            
            original_text = active_msg['content']
            
            if SETTINGS.get('anti_detection', True):
                variations = anti_detection.get_variation(original_text, 6)
                logger.info(f"📝 تم توليد {len(variations)} تنويع")
            else:
                variations = [original_text]
            
            accounts_list = list(USER_CLIENTS.items())
            
            for phone, client in accounts_list:
                if not is_posting:
                    break
                
                try:
                    groups_sent = 0
                    groups_list = []
                    
                    async for dialog in client.iter_dialogs():
                        if dialog.is_group and groups_sent < 50:
                            groups_list.append(dialog)
                    
                    random.shuffle(groups_list)
                    
                    for dialog in groups_list:
                        if not is_posting:
                            break
                        
                        blacklisted = [g[0] for g in db.get_blacklisted_groups()]
                        if str(dialog.id) in blacklisted:
                            continue
                        
                        if group_blacklist.is_banned(str(dialog.id)):
                            continue
                        
                        db.add_group(dialog.id, dialog.name, 
                                   getattr(dialog.entity, 'username', None),
                                   'group', 
                                   getattr(dialog.entity, 'participants_count', 0), 
                                   phone)
                        
                        selected_text = random.choice(variations)
                        
                        if SETTINGS.get('anti_detection', True):
                            success, result = await anti_detection.send_safe(
                                client, dialog.id, selected_text, dialog.name
                            )
                        else:
                            try:
                                await client.send_message(dialog.id, selected_text)
                                success, result = True, "OK"
                            except Exception as e:
                                success, result = False, str(e)
                        
                        if success:
                            db.log_post(phone, dialog.id, dialog.name, 'success')
                            groups_sent += 1
                            stats['success'] += 1
                            group_blacklist.clear_banned(str(dialog.id))
                            logger.info(f"✅ [{phone[-8:]}] أرسل لـ {dialog.name[:30]}")
                        else:
                            stats['failed'] += 1
                            logger.warning(f"⚠️ فشل لـ {dialog.name[:30]}: {result[:50]}")
                            if "banned" in result.lower() or "can't write" in result.lower():
                                group_blacklist.record_failure(str(dialog.id), result)
                        
                        stats['total'] += 1
                        
                        delay = anti_detection.random_delay(SETTINGS.get('interval', 12))
                        await asyncio.sleep(delay)
                    
                    logger.info(f"📊 [{phone[-8:]}] أرسل {groups_sent} رسالة")
                    
                except Exception as e:
                    logger.error(f"❌ خطأ في الحساب {phone[-8:]}: {e}")
                    db.update_account_status(phone, 'error')
            
            logger.info(f"📈 إحصائيات الدورة: {stats['success']} نجاح / {stats['failed']} فشل")
            
            cycle_wait = random.randint(90, 180)
            logger.info(f"⏸ استراحة {cycle_wait} ثانية...")
            await asyncio.sleep(cycle_wait)
            
        except Exception as e:
            logger.error(f"💥 خطأ في حلقة النشر: {e}")
            await asyncio.sleep(30)

# استعادة الجلسات
async def restore_sessions():
    restored = 0
    accounts = db.get_accounts()
    logger.info(f"🔍 محاولة استعادة {len(accounts)} حساب...")
    
    for account in accounts:
        try:
            if len(account) < 2:
                continue
            phone = account[0]
            session_str = None
            
            conn = sqlite3.connect(DB_PATH, timeout=15)
            try:
                result = conn.execute('SELECT session_str FROM accounts WHERE phone = ?', (phone,)).fetchone()
                if result and result[0]:
                    session_str = result[0]
            finally:
                conn.close()
            
            if not session_str:
                logger.warning(f"⚠️ لا توجد جلسة للحساب {phone}")
                continue
            
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.connect()
            
            if await client.is_user_authorized():
                USER_CLIENTS[phone] = client
                db.update_account_status(phone, 'active')
                restored += 1
                logger.success(f"✅ تم استعادة {phone}")
            else:
                db.update_account_status(phone, 'unauthorized')
                logger.warning(f"⚠️ الحساب {phone} غير مصرح به")
                
        except Exception as e:
            logger.error(f"❌ فشل استعادة حساب: {e}")
            if len(account) > 0:
                db.update_account_status(account[0], 'error')
    
    logger.info(f"✅ تم استعادة {restored} من أصل {len(accounts)} حساب")
    return restored

# ==================== التشغيل الرئيسي ====================

async def main():
    global bot, start_time
    start_time = datetime.now()
    
    # تشغيل خادم الويب (سيتم استخدامه بواسطة Procfile)
    Thread(target=run_web, daemon=True).start()
    print("🌐 خادم الويب يعمل على المنفذ 10000")
    
    print("🚀 جاري تشغيل البوت...")
    print("👤 ADMIN_ID المستخدم:", ADMIN_ID)
    
    await restore_sessions()
    
    bot = TelegramClient('bot_session', API_ID, API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    
    me = await bot.get_me()
    print(f"✅ البوت متصل: @{me.username}")
    print(f"👤 آيدي البوت: {me.id}")
    
    @bot.on(events.NewMessage(pattern='/start'))
    async def start(e):
        await start_handler(e)
    
    @bot.on(events.CallbackQuery())
    async def callback(e):
        await callback_handler(e)
    
    @bot.on(events.NewMessage)
    async def text(e):
        if e.message.text and e.sender_id == ADMIN_ID:
            state = TEMP.get(ADMIN_ID)
            if isinstance(state, dict) and state.get("s") == "code":
                await handle_code_verification(e, state, e.message.text.strip())
            elif isinstance(state, dict) and state.get("s") == "pass":
                await handle_password(e, state, e.message.text.strip())
            else:
                await text_handler(e)
        elif e.is_group and e.message.text:
            await text_handler(e)
    
    logger.success("✅ البوت جاهز! أرسل /start")
    print("🎉 البوت يعمل مع نظام الانضمام البطيء جداً")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 تم إيقاف البوت")
    except Exception as e:
        logger.critical(f"💥 خطأ: {e}")
        time.sleep(5)
        os.execl(sys.executable, sys.executable, *sys.argv)
