#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════╗
║     🤖 بوت النشر الخارق - نسخة نظيفة بدون قفل 🚀            ║
║     يدعم SQLite محلية + PostgreSQL خارجية (اختياري)         ║
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

API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', "")
BOT_TOKEN = os.environ.get('BOT_TOKEN', "")
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
PORT = int(os.environ.get('PORT', 10000))

DATABASE_URL = os.environ.get('DATABASE_URL', None)

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
    uptime_val = str(datetime.now() - start_time) if 'start_time' in globals() else "جاري الحساب"
    return jsonify({
        'status': 'online',
        'msg': '🤖 البوت يعمل بنجاح!',
        'time': str(datetime.now()),
        'db_type': 'PostgreSQL خارجية' if DATABASE_URL else 'SQLite محلية',
        'version': '5.0.0'
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'port': PORT}), 200

def run_web():
    """تشغيل خادم الويب"""
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 [WEB] بدء تشغيل Flask على المنفذ {port}...")
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

# ==================== نظام التشفير الذكي ====================

class SmartEncryption:
    """تشفير ذكي يحافظ على الروابط واليوزرات والأرقام"""
    
    ZERO_WIDTH = ['\u200B', '\u200C', '\u200D', '\uFEFF', '\u2060']
    DIACRITICS = ['\u064E', '\u064F', '\u0650', '\u0651', '\u0652']
    
    @classmethod
    def is_arabic_char(cls, char):
        return '\u0600' <= char <= '\u06FF' or char in 'ابتثجحخدذرزسشصضطظعغفقكلمنهوي'
    
    @classmethod
    def is_safe_char(cls, char):
        safe = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@._-/:?=&'
        return char in safe or char in '.,!?;:()[]{}\'"<>|\\/*-+=~`#$%^&*'
    
    @classmethod
    def encrypt(cls, text):
        if not SETTINGS.get('encryption', True) or not text:
            return text
        
        result = []
        for char in text:
            if cls.is_safe_char(char):
                result.append(char)
            elif cls.is_arabic_char(char):
                result.append(char)
                if random.random() < 0.4:
                    result.append(random.choice(cls.ZERO_WIDTH))
                if random.random() < 0.15:
                    result.append(random.choice(cls.DIACRITICS))
            else:
                result.append(char)
        return ''.join(result)

def encrypt_text(text):
    return SmartEncryption.encrypt(text)

# ==================== قاعدة البيانات ====================

class Database:
    def __init__(self):
        self.db_type = 'postgres' if DATABASE_URL else 'sqlite'
        self.db_path = DB_PATH
        self.pg_pool = None
        
        if self.db_type == 'sqlite':
            self._init_sqlite()
    
    def _init_sqlite(self):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            c = conn.cursor()
            self._create_tables_sync(c)
            conn.commit()
            conn.close()
            logger.success("✅ قاعدة البيانات المحلية (SQLite) جاهزة")
            
            if not self._get_all_messages_sync():
                default_msg = "📢 **مرحباً بك في البوت!**\n\nهذه رسالة تجريبية للنشر في المجموعات.\nيمكنك تغييرها من خلال قائمة إدارة الرسائل."
                self._save_message_sync("default", default_msg, is_active=True)
    
    async def init_postgres(self):
        if self.db_type != 'postgres':
            return
        try:
            import asyncpg
            self.pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
            async with self.pg_pool.acquire() as conn:
                await conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMPTZ DEFAULT NOW())")
                await conn.execute("CREATE TABLE IF NOT EXISTS messages (msg_id TEXT PRIMARY KEY, content TEXT, created_at TIMESTAMPTZ DEFAULT NOW(), is_active INTEGER DEFAULT 0)")
                await conn.execute("CREATE TABLE IF NOT EXISTS accounts (phone TEXT PRIMARY KEY, session_str TEXT, added_at TIMESTAMPTZ DEFAULT NOW(), last_active TIMESTAMPTZ DEFAULT NOW(), status TEXT DEFAULT 'active', total_posts INTEGER DEFAULT 0, success_posts INTEGER DEFAULT 0, failed_posts INTEGER DEFAULT 0)")
                await conn.execute("CREATE TABLE IF NOT EXISTS groups (group_id TEXT PRIMARY KEY, group_name TEXT, group_username TEXT, group_type TEXT, members_count INTEGER DEFAULT 0, added_by TEXT, added_at TIMESTAMPTZ DEFAULT NOW(), last_post TIMESTAMPTZ, post_count INTEGER DEFAULT 0, is_blacklisted INTEGER DEFAULT 0)")
                await conn.execute("CREATE TABLE IF NOT EXISTS posting_history (id SERIAL PRIMARY KEY, phone TEXT, group_id TEXT, group_name TEXT, sent_at TIMESTAMPTZ DEFAULT NOW(), status TEXT, error TEXT)")
                await conn.execute("CREATE TABLE IF NOT EXISTS joined_links (id SERIAL PRIMARY KEY, link TEXT, group_id TEXT, group_name TEXT, joined_at TIMESTAMPTZ DEFAULT NOW(), joined_by TEXT)")
                await conn.execute("CREATE TABLE IF NOT EXISTS contacts (id SERIAL PRIMARY KEY, name TEXT, phone TEXT, telegram_id TEXT, added_at TIMESTAMPTZ DEFAULT NOW())")
            logger.success("✅ قاعدة البيانات الخارجية (PostgreSQL) جاهزة")
        except ImportError:
            logger.error("❌ مكتبة asyncpg غير مثبتة")
            self.db_type = 'sqlite'
            self._init_sqlite()
        except Exception as e:
            logger.error(f"❌ فشل الاتصال بـ PostgreSQL: {e}")
            self.db_type = 'sqlite'
            self._init_sqlite()
    
    def _create_tables_sync(self, c):
        c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS messages (msg_id TEXT PRIMARY KEY, content TEXT, created_at TIMESTAMP, is_active INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS accounts (phone TEXT PRIMARY KEY, session_str TEXT, added_at TIMESTAMP, last_active TIMESTAMP, status TEXT, total_posts INTEGER DEFAULT 0, success_posts INTEGER DEFAULT 0, failed_posts INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS groups (group_id TEXT PRIMARY KEY, group_name TEXT, group_username TEXT, group_type TEXT, members_count INTEGER DEFAULT 0, added_by TEXT, added_at TIMESTAMP, last_post TIMESTAMP, post_count INTEGER DEFAULT 0, is_blacklisted INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS posting_history (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, group_id TEXT, group_name TEXT, sent_at TIMESTAMP, status TEXT, error TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS joined_links (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, group_id TEXT, group_name TEXT, joined_at TIMESTAMP, joined_by TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT, telegram_id TEXT, added_at TIMESTAMP)''')
    
    def _get_all_messages_sync(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT msg_id, content, is_active FROM messages ORDER BY created_at DESC').fetchall()
        finally:
            conn.close()
    
    def _save_message_sync(self, msg_id, content, is_active=False):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                if is_active:
                    conn.execute('UPDATE messages SET is_active = 0')
                conn.execute('INSERT OR REPLACE INTO messages (msg_id, content, created_at, is_active) VALUES (?, ?, ?, ?)', 
                            (msg_id, content, datetime.now(), 1 if is_active else 0))
                conn.commit()
            finally:
                conn.close()
    
    def save_setting(self, key, value):
        if self.db_type == 'sqlite':
            with db_lock:
                conn = sqlite3.connect(self.db_path, timeout=15)
                try:
                    conn.execute('INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)', 
                                (key, json.dumps(value, ensure_ascii=False), datetime.now()))
                    conn.commit()
                finally:
                    conn.close()
    
    def get_setting(self, key, default=None):
        if self.db_type == 'sqlite':
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                result = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
                return json.loads(result[0]) if result else default
            finally:
                conn.close()
        return default
    
    def get_all_settings(self):
        if self.db_type == 'sqlite':
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                rows = conn.execute('SELECT key, value FROM settings').fetchall()
                return {key: json.loads(value) for key, value in rows}
            finally:
                conn.close()
        return {}
    
    def save_message(self, msg_id, content, is_active=False):
        if self.db_type == 'sqlite':
            self._save_message_sync(msg_id, content, is_active)
    
    def get_all_messages(self):
        if self.db_type == 'sqlite':
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                return conn.execute('SELECT msg_id, content, is_active FROM messages ORDER BY created_at DESC').fetchall()
            finally:
                conn.close()
        return []
    
    def get_active_message(self):
        if self.db_type == 'sqlite':
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
        return None
    
    def set_active_message(self, msg_id):
        if self.db_type == 'sqlite':
            with db_lock:
                conn = sqlite3.connect(self.db_path, timeout=15)
                try:
                    conn.execute('UPDATE messages SET is_active = 0')
                    conn.execute('UPDATE messages SET is_active = 1 WHERE msg_id = ?', (msg_id,))
                    conn.commit()
                finally:
                    conn.close()
    
    def delete_message(self, msg_id):
        if self.db_type == 'sqlite':
            with db_lock:
                conn = sqlite3.connect(self.db_path, timeout=15)
                try:
                    conn.execute('DELETE FROM messages WHERE msg_id = ?', (msg_id,))
                    conn.commit()
                finally:
                    conn.close()
    
    def add_account(self, phone, session_str):
        if self.db_type == 'sqlite':
            with db_lock:
                conn = sqlite3.connect(self.db_path, timeout=15)
                try:
                    conn.execute('INSERT OR REPLACE INTO accounts (phone, session_str, added_at, last_active, status) VALUES (?, ?, ?, ?, ?)', 
                                (phone, session_str, datetime.now(), datetime.now(), 'active'))
                    conn.commit()
                finally:
                    conn.close()
        logger.success(f"✅ تم إضافة الحساب: {phone}")
    
    def remove_account(self, phone):
        if self.db_type == 'sqlite':
            with db_lock:
                conn = sqlite3.connect(self.db_path, timeout=15)
                try:
                    conn.execute('DELETE FROM accounts WHERE phone = ?', (phone,))
                    conn.commit()
                finally:
                    conn.close()
    
    def get_accounts(self):
        if self.db_type == 'sqlite':
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                return conn.execute('SELECT phone, status, total_posts, success_posts, failed_posts FROM accounts ORDER BY added_at DESC').fetchall()
            finally:
                conn.close()
        return []
    
    def get_account_session(self, phone):
        if self.db_type == 'sqlite':
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                result = conn.execute('SELECT session_str FROM accounts WHERE phone = ?', (phone,)).fetchone()
                return result[0] if result else None
            finally:
                conn.close()
        return None
    
    def add_group(self, group_id, group_name, group_username, group_type, members_count, added_by):
        if self.db_type == 'sqlite':
            with db_lock:
                conn = sqlite3.connect(self.db_path, timeout=15)
                try:
                    conn.execute('INSERT OR IGNORE INTO groups (group_id, group_name, group_username, group_type, members_count, added_by, added_at) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                                (str(group_id), group_name or "بدون اسم", group_username or "", group_type, members_count or 0, added_by, datetime.now()))
                    conn.commit()
                finally:
                    conn.close()
    
    def update_group_post(self, group_id):
        if self.db_type == 'sqlite':
            with db_lock:
                conn = sqlite3.connect(self.db_path, timeout=15)
                try:
                    conn.execute('UPDATE groups SET post_count = post_count + 1, last_post = ? WHERE group_id = ?', 
                                (datetime.now(), str(group_id)))
                    conn.commit()
                finally:
                    conn.close()
    
    def blacklist_group(self, group_id):
        if self.db_type == 'sqlite':
            with db_lock:
                conn = sqlite3.connect(self.db_path, timeout=15)
                try:
                    conn.execute('UPDATE groups SET is_blacklisted = 1 WHERE group_id = ?', (str(group_id),))
                    conn.commit()
                finally:
                    conn.close()
    
    def whitelist_group(self, group_id):
        if self.db_type == 'sqlite':
            with db_lock:
                conn = sqlite3.connect(self.db_path, timeout=15)
                try:
                    conn.execute('UPDATE groups SET is_blacklisted = 0 WHERE group_id = ?', (str(group_id),))
                    conn.commit()
                finally:
                    conn.close()
    
    def get_all_groups(self):
        if self.db_type == 'sqlite':
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                return conn.execute('SELECT group_id, group_name, members_count, post_count, is_blacklisted, last_post FROM groups ORDER BY post_count DESC').fetchall()
            finally:
                conn.close()
        return []
    
    def get_blacklisted_groups(self):
        if self.db_type == 'sqlite':
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                return conn.execute('SELECT group_id, group_name FROM groups WHERE is_blacklisted = 1').fetchall()
            finally:
                conn.close()
        return []
    
    def log_post(self, phone, group_id, group_name, status='success', error=None):
        if self.db_type == 'sqlite':
            with db_lock:
                conn = sqlite3.connect(self.db_path, timeout=15)
                try:
                    conn.execute('INSERT INTO posting_history (phone, group_id, group_name, sent_at, status, error) VALUES (?, ?, ?, ?, ?, ?)', 
                                (phone, str(group_id), group_name[:50], datetime.now(), status, error))
                    if status == 'success':
                        self._increment_account_posts_sync(phone, success=True)
                        self.update_group_post(group_id)
                    else:
                        self._increment_account_posts_sync(phone, success=False)
                    conn.commit()
                finally:
                    conn.close()
    
    def _increment_account_posts_sync(self, phone, success=True):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            if success:
                conn.execute('UPDATE accounts SET total_posts = total_posts + 1, success_posts = success_posts + 1 WHERE phone = ?', (phone,))
            else:
                conn.execute('UPDATE accounts SET total_posts = total_posts + 1, failed_posts = failed_posts + 1 WHERE phone = ?', (phone,))
            conn.commit()
        finally:
            conn.close()
    
    def get_posting_stats(self, hours=24):
        if self.db_type == 'sqlite':
            since = datetime.now() - timedelta(hours=hours)
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                total = conn.execute('SELECT COUNT(*) FROM posting_history WHERE sent_at > ?', (since,)).fetchone()[0]
                success = conn.execute("SELECT COUNT(*) FROM posting_history WHERE sent_at > ? AND status = 'success'", (since,)).fetchone()[0]
                failed = conn.execute("SELECT COUNT(*) FROM posting_history WHERE sent_at > ? AND status = 'failed'", (since,)).fetchone()[0]
                return {'total': total, 'success': success, 'failed': failed}
            finally:
                conn.close()
        return {'total': 0, 'success': 0, 'failed': 0}
    
    def get_recent_posts(self, limit=10):
        if self.db_type == 'sqlite':
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                return conn.execute('SELECT phone, group_name, status, sent_at FROM posting_history ORDER BY sent_at DESC LIMIT ?', (limit,)).fetchall()
            finally:
                conn.close()
        return []
    
    def add_joined_link(self, link, group_id, group_name, joined_by):
        if self.db_type == 'sqlite':
            with db_lock:
                conn = sqlite3.connect(self.db_path, timeout=15)
                try:
                    conn.execute('INSERT INTO joined_links (link, group_id, group_name, joined_at, joined_by) VALUES (?, ?, ?, ?, ?)', 
                                (link, str(group_id), group_name[:50], datetime.now(), joined_by))
                    conn.commit()
                finally:
                    conn.close()
    
    def get_joined_links(self, limit=100):
        if self.db_type == 'sqlite':
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                return conn.execute('SELECT link, group_name, joined_at, joined_by FROM joined_links ORDER BY joined_at DESC LIMIT ?', (limit,)).fetchall()
            finally:
                conn.close()
        return []
    
    def get_joined_links_count(self):
        if self.db_type == 'sqlite':
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                return conn.execute('SELECT COUNT(*) FROM joined_links').fetchone()[0]
            finally:
                conn.close()
        return 0
    
    def add_contact(self, name, phone, telegram_id=""):
        if self.db_type == 'sqlite':
            with db_lock:
                conn = sqlite3.connect(self.db_path, timeout=15)
                try:
                    conn.execute('INSERT INTO contacts (name, phone, telegram_id, added_at) VALUES (?, ?, ?, ?)', 
                                (name, phone, telegram_id, datetime.now()))
                    conn.commit()
                finally:
                    conn.close()
    
    def get_contacts(self):
        if self.db_type == 'sqlite':
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                return conn.execute('SELECT id, name, phone, telegram_id, added_at FROM contacts ORDER BY added_at DESC').fetchall()
            finally:
                conn.close()
        return []
    
    def delete_contact(self, contact_id):
        if self.db_type == 'sqlite':
            with db_lock:
                conn = sqlite3.connect(self.db_path, timeout=15)
                try:
                    conn.execute('DELETE FROM contacts WHERE id = ?', (contact_id,))
                    conn.commit()
                finally:
                    conn.close()
    
    def create_backup(self):
        if self.db_type == 'sqlite':
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f"{BACKUPS_DIR}/backup_{timestamp}.db"
            with db_lock:
                shutil.copy2(self.db_path, backup_file)
            backups = sorted(Path(BACKUPS_DIR).glob('backup_*.db'))
            if len(backups) > 20:
                for old in backups[:-20]:
                    old.unlink()
            logger.success(f"💾 تم إنشاء نسخة احتياطية: {backup_file}")
            return backup_file
        return None

# ==================== المتغيرات العامة ====================

USER_CLIENTS = {}
SETTINGS = {
    'interval': 5,
    'encryption': True,
    'auto_join_enabled': True,
    'save_joined_links': True,
    'anti_detection': True,
    'warm_up_enabled': False
}
TEMP = {}
is_posting = False
bot = None
db = None
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
    active_msg = db.get_active_message()
    msg_preview = active_msg['content'][:20] + "..." if active_msg and len(active_msg['content']) > 20 else (active_msg['content'][:20] if active_msg else "لا يوجد")
    
    return [
        [Button.inline("➕ إضافة حساب", b"add"), Button.inline("🗑 حذف حساب", b"del_list")],
        [Button.inline("📝 إدارة الرسائل", b"manage_messages"), Button.inline("⏱ ضبط الوقت", b"time")],
        [Button.inline(f"📨 {msg_preview}", b"show_active")],
        [Button.inline("🚀 بدء النشر", b"start_p"), Button.inline("🛑 إيقاف النشر", b"stop_p")],
        [Button.inline(f"🛡 التشفير: {enc_status}", b"toggle_enc"), Button.inline("📊 الحالة", b"status")],
        [Button.inline("📢 المجموعات", b"view_chats"), Button.inline("⚙️ إعدادات متقدمة", b"advanced")],
        [Button.inline("📈 إحصائيات", b"stats"), Button.inline("🔗 الروابط", b"view_joined_links")],
        [Button.inline("📊 تقارير", b"real_reports")],
        [Button.inline("📞 جهات الاتصال", b"contacts_menu")]
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
        [Button.inline("🔄 إعادة تشغيل", b"restart")],
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

def contacts_buttons():
    return [
        [Button.inline("➕ إضافة جهة اتصال", b"add_contact")],
        [Button.inline("📋 عرض جهات الاتصال", b"list_contacts")],
        [Button.inline("🗑 حذف جهة اتصال", b"delete_contact")],
        [Button.inline("📨 إرسال رسالة", b"message_contact")],
        [Button.inline("⬅️ عودة", b"back")]
    ]

# ==================== معالج البداية (بدون قفل) ====================

async def start_handler(event):
    """معالج أمر /start - بدون أي فحص للقنوات أو الاشتراكات"""
    if event.sender_id != ADMIN_ID:
        await event.respond("❌ غير مصرح لك باستخدام هذا البوت!")
        return
    
    accounts = db.get_accounts()
    groups = db.get_all_groups()
    joined_links = db.get_joined_links_count()
    active_msg = db.get_active_message()
    
    db_type_text = "🗄️ PostgreSQL خارجية" if DATABASE_URL else "📁 SQLite محلية"
    
    await event.respond(
        f"👋 **أهلاً بك في بوت النشر الخارق!**\n\n"
        f"{db_type_text}\n"
        f"🔐 **التشفير:** ذكي (يحافظ على الروابط)\n"
        f"📊 **الإحصائيات:**\n"
        f"• الحسابات: {len(accounts)}\n"
        f"• المجموعات: {len(groups)}\n"
        f"• المحظورات: {len(db.get_blacklisted_groups())}\n"
        f"• الروابط المنضم لها: {joined_links}\n"
        f"• الرسائل المحفوظة: {len(db.get_all_messages())}\n\n"
        f"📨 **الرسالة النشطة:**\n{active_msg['content'][:100] if active_msg else 'لا توجد'}\n\n"
        f"استخدم الأزرار للتحكم:", 
        buttons=main_buttons()
    )

# ==================== معالج الأزرار (بدون قفل) ====================

async def callback_handler(event):
    global SETTINGS, is_posting
    
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ غير مصرح لك!", alert=True)
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
        await event.edit("⏱ أرسل الفاصل الزمني (3-60 ثانية):"); 
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
            "⚠️ **تحذير!** ⚠️\n\nأنت على وشك حذف قاعدة البيانات بالكامل!\n\nهل أنت متأكد؟",
            buttons=[
                [Button.inline("✅ نعم، احذف كل شيء", b"confirm_delete_db")],
                [Button.inline("❌ إلغاء", b"advanced")]
            ]
        )
    elif data == "confirm_delete_db":
        try:
            if DATABASE_URL:
                await event.edit("⚠️ لا يمكن حذف قاعدة البيانات الخارجية من هنا.", buttons=[[Button.inline("⬅️ عودة", b"advanced")]])
                return
            db.create_backup()
            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
            db._init_sqlite()
            await event.edit("✅ **تم حذف قاعدة البيانات بنجاح!**", buttons=[[Button.inline("🔄 العودة للقائمة", b"back")]])
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
    elif data == "contacts_menu":
        await event.edit("📞 **جهات الاتصال**\n\nاختر الإجراء المطلوب:", buttons=contacts_buttons())
    elif data == "add_contact":
        await event.edit("📱 **إضافة جهة اتصال جديدة**\n\nأرسل الاسم ثم رقم الهاتف\nمثال: أحمد +967712345678")
        TEMP[ADMIN_ID] = {"state": "add_contact"}
    elif data == "list_contacts":
        await show_contacts_list(event)
    elif data == "delete_contact":
        await show_delete_contact(event)
    elif data == "message_contact":
        await show_message_contact(event)
    elif data == "start_p":
        if not USER_CLIENTS:
            return await event.answer("❌ لا توجد حسابات!", alert=True)
        active_msg = db.get_active_message()
        if not active_msg:
            return await event.answer("❌ لا توجد رسالة نشطة!", alert=True)
        if is_posting:
            return await event.answer("⚠️ النشر يعمل بالفعل!", alert=True)
        is_posting = True
        asyncio.create_task(poster())
        await event.edit("🚀 بدأ النشر", buttons=main_buttons())
    elif data == "stop_p":
        if not is_posting:
            return await event.answer("⚠️ النشر متوقف بالفعل!", alert=True)
        is_posting = False
        await event.edit("🛑 تم إيقاف النشر", buttons=main_buttons())
    elif data.startswith("del_contact_"):
        contact_id = int(data.replace("del_contact_", ""))
        db.delete_contact(contact_id)
        await event.answer("✅ تم حذف جهة الاتصال", alert=True)
        await show_delete_contact(event)
    elif data.startswith("msg_contact_"):
        contact_id = int(data.replace("msg_contact_", ""))
        contacts = db.get_contacts()
        contact = next((c for c in contacts if c[0] == contact_id), None)
        if contact:
            active_msg = db.get_active_message()
            if active_msg:
                await event.edit(f"📨 سيتم إرسال الرسالة إلى **{contact[1]}**\n\nأرسل الرسالة الآن:")
                TEMP[ADMIN_ID] = {"state": "send_to_contact", "contact_id": contact_id, "phone": contact[2]}
            else:
                await event.answer("❌ لا توجد رسالة نشطة", alert=True)
        else:
            await event.answer("❌ جهة الاتصال غير موجودة", alert=True)

# ==================== دوال العرض ====================

async def list_all_messages(event):
    messages = db.get_all_messages()
    if not messages:
        await event.edit("📭 لا توجد رسائل", buttons=messages_buttons())
        return
    text = "📋 **جميع الرسائل**\n\n"
    for i, (msg_id, content, is_active) in enumerate(messages[:10], 1):
        status = "🌟" if is_active else "📄"
        text += f"{i}. {status} {content[:40]}...\n"
    await event.edit(text, buttons=messages_buttons())

async def show_set_active_message(event):
    messages = db.get_all_messages()
    if not messages:
        await event.answer("❌ لا توجد رسائل!", alert=True)
        return
    btns = []
    for msg_id, content, is_active in messages[:10]:
        preview = content[:25]
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
        preview = content[:25]
        btns.append([Button.inline(f"🗑 {preview}", f"del_msg_{msg_id}".encode())])
    btns.append([Button.inline("⬅️ عودة", b"manage_messages")])
    await event.edit("🗑 اختر رسالة للحذف", buttons=btns)

async def show_status(event):
    accounts = db.get_accounts()
    groups = db.get_all_groups()
    stats = db.get_posting_stats()
    active_accounts = len([a for a in accounts if a[1] == 'active'])
    db_type = "PostgreSQL" if DATABASE_URL else "SQLite"
    uptime = datetime.now() - start_time
    hours = int(uptime.total_seconds() // 3600)
    minutes = int((uptime.total_seconds() % 3600) // 60)
    
    text = f"📊 **حالة البوت**\n\n"
    text += f"🗄️ القاعدة: {db_type}\n"
    text += f"⏰ وقت التشغيل: {hours}س {minutes}د\n"
    text += f"👤 الحسابات: {active_accounts}/{len(accounts)}\n"
    text += f"📨 منشورات اليوم: {stats['total']}\n"
    text += f"✅ الناجح: {stats['success']}\n"
    text += f"❌ الفاشل: {stats['failed']}\n"
    text += f"📢 المجموعات: {len(groups)}\n"
    text += f"🚫 المحظورات: {len(db.get_blacklisted_groups())}\n"
    text += f"🔄 النشر: {'🟢 نشط' if is_posting else '🔴 متوقف'}\n"
    
    await event.edit(text, buttons=main_buttons())

async def show_stats(event):
    stats = db.get_posting_stats()
    recent = db.get_recent_posts(5)
    text = f"📈 **إحصائيات 24 ساعة**\n\n"
    text += f"✅ الناجح: {stats['success']}\n❌ الفاشل: {stats['failed']}\n📊 الإجمالي: {stats['total']}\n\n"
    text += f"📋 **آخر 5 عمليات:**\n"
    for phone, group, status, sent_at in recent:
        icon = "✅" if status == 'success' else "❌"
        text += f"{icon} {group[:20]}\n"
    await event.edit(text, buttons=main_buttons())

async def show_groups(event):
    groups = db.get_all_groups()
    text = f"📢 **المجموعات** ({len(groups)})\n\n"
    for gid, name, members, posts, bl, last in groups[:15]:
        status = "🚫" if bl else "✅"
        text += f"{status} {name[:25]} | 👥 {members or '?'}\n"
    await event.edit(text, buttons=main_buttons())

async def show_delete_list(event):
    accounts = db.get_accounts()
    if not accounts:
        return await event.answer("❌ لا توجد حسابات", alert=True)
    btns = []
    for phone, status, posts, success, failed in accounts[:10]:
        short = phone[-8:]
        btns.append([Button.inline(f"{'🟢' if status=='active' else '🔴'} {short}", f"rm_{phone}".encode())])
    btns.append([Button.inline("⬅️ عودة", b"back")])
    await event.edit("🗑 اختر حساباً للحذف", buttons=btns)

async def show_blacklist(event):
    blacklisted = db.get_blacklisted_groups()
    if not blacklisted:
        await event.edit("📭 لا توجد محظورات", buttons=blacklist_buttons())
        return
    text = "🚫 **المحظورات**\n\n"
    for gid, name in blacklisted[:20]:
        text += f"• {name[:30]}\n"
    await event.edit(text, buttons=blacklist_buttons())

async def show_remove_blacklist(event):
    blacklisted = db.get_blacklisted_groups()
    if not blacklisted:
        return await event.answer("❌ لا توجد محظورات", alert=True)
    btns = []
    for gid, name in blacklisted[:10]:
        btns.append([Button.inline(f"✅ {name[:20]}", f"unblack_{gid}".encode())])
    btns.append([Button.inline("⬅️ عودة", b"blacklist_menu")])
    await event.edit("✅ اختر للإزالة", buttons=btns)

async def show_real_stats(event):
    stats = db.get_posting_stats(24)
    recent = db.get_recent_posts(5)
    text = f"📊 **إحصائيات**\n✅ {stats['success']} | ❌ {stats['failed']}\n\n"
    for phone, group, status, sent_at in recent:
        text += f"{'✅' if status=='success' else '❌'} {group[:20]}\n"
    await event.edit(text, buttons=reports_buttons())

async def show_accounts_report(event):
    accounts = db.get_accounts()
    text = "👥 **الحسابات**\n\n"
    for phone, status, total, success, failed in accounts[:10]:
        text += f"{'🟢' if status=='active' else '🔴'} {phone[-8:]}: {success}/{total}\n"
    await event.edit(text, buttons=reports_buttons())

async def show_groups_report(event):
    groups = db.get_all_groups()
    text = f"📢 **المجموعات** ({len(groups)})\n\n"
    for gid, name, members, posts, bl, last in groups[:10]:
        text += f"• {name[:25]}: {posts} منشور\n"
    await event.edit(text, buttons=reports_buttons())

async def show_links_report(event):
    links = db.get_joined_links(20)
    text = f"🔗 **الروابط** ({len(links)})\n\n"
    for link, group_name, joined_at, joined_by in links[:10]:
        text += f"• {group_name[:25]}\n"
    await event.edit(text, buttons=reports_buttons())

async def show_detailed_stats(event):
    accounts = db.get_accounts()
    text = "📊 **تفصيلية**\n\n"
    for phone, status, total, success, failed in accounts[:5]:
        rate = (success/total*100) if total > 0 else 0
        text += f"• {phone[-8:]}: {rate:.1f}%\n"
    await event.edit(text, buttons=advanced_buttons())

async def show_posting_history(event):
    recent = db.get_recent_posts(15)
    text = "📋 **آخر النشر**\n\n"
    for phone, group, status, sent_at in recent:
        text += f"{'✅' if status=='success' else '❌'} {group[:20]}\n"
    await event.edit(text, buttons=advanced_buttons())

async def show_group_stats(event):
    groups = db.get_all_groups()
    text = "📊 **إحصائيات المجموعات**\n\n"
    for gid, name, members, posts, bl, last in groups[:10]:
        text += f"• {name[:25]}: {posts}\n"
    await event.edit(text, buttons=groups_buttons())

async def show_joined_links(event):
    links = db.get_joined_links(20)
    if not links:
        await event.edit("📭 لا توجد روابط", buttons=main_buttons())
        return
    text = "🔗 **الروابط**\n\n"
    for link, group_name, joined_at, joined_by in links[:15]:
        text += f"• {group_name[:30]}\n"
    await event.edit(text, buttons=main_buttons())

async def show_contacts_list(event):
    contacts = db.get_contacts()
    if not contacts:
        await event.edit("📭 لا توجد جهات اتصال", buttons=contacts_buttons())
        return
    text = "📞 **جهات الاتصال**\n\n"
    for cid, name, phone, tg_id, added_at in contacts[:15]:
        text += f"• {name}: {phone}\n"
    await event.edit(text, buttons=contacts_buttons())

async def show_delete_contact(event):
    contacts = db.get_contacts()
    if not contacts:
        await event.answer("❌ لا توجد جهات اتصال!", alert=True)
        return
    btns = []
    for cid, name, phone, tg_id, added_at in contacts[:10]:
        btns.append([Button.inline(f"🗑 {name[:20]}", f"del_contact_{cid}".encode())])
    btns.append([Button.inline("⬅️ عودة", b"contacts_menu")])
    await event.edit("🗑 اختر للحذف", buttons=btns)

async def show_message_contact(event):
    contacts = db.get_contacts()
    if not contacts:
        await event.answer("❌ لا توجد جهات اتصال!", alert=True)
        return
    btns = []
    for cid, name, phone, tg_id, added_at in contacts[:10]:
        btns.append([Button.inline(f"📨 {name[:20]}", f"msg_contact_{cid}".encode())])
    btns.append([Button.inline("⬅️ عودة", b"contacts_menu")])
    await event.edit("📨 اختر للإرسال", buttons=btns)

# ==================== دوال الإجراءات ====================

async def delete_account(event, phone):
    if phone in USER_CLIENTS:
        try: await USER_CLIENTS[phone].disconnect()
        except: pass
        del USER_CLIENTS[phone]
    db.remove_account(phone)
    await event.answer(f"✅ تم حذف {phone}", alert=True)
    await show_delete_list(event)

async def remove_from_blacklist(event, group_id):
    db.whitelist_group(group_id)
    group_blacklist.clear_banned(group_id)
    await event.answer("✅ تمت الإزالة", alert=True)
    await show_remove_blacklist(event)

async def refresh_groups(event):
    await event.edit("🔄 جاري التحديث...")
    await asyncio.sleep(1)
    groups = db.get_all_groups()
    await event.edit(f"✅ تم التحديث ({len(groups)})", buttons=groups_buttons())

async def create_backup_handler(event):
    if DATABASE_URL:
        await event.answer("⚠️ النسخ الاحتياطي متاح فقط لـ SQLite", alert=True)
        return
    backup_file = db.create_backup()
    await event.answer(f"✅ تم النسخ:\n{backup_file}", alert=True)

# ==================== النشر ====================

async def poster():
    global is_posting
    logger.info("🚀 بدء النشر...")
    
    while is_posting:
        try:
            groups = db.get_all_groups()
            active_msg = db.get_active_message()
            
            if not groups or not active_msg or not USER_CLIENTS:
                await asyncio.sleep(10)
                continue
            
            phone = random.choice(list(USER_CLIENTS.keys()))
            client = USER_CLIENTS.get(phone)
            if not client:
                continue
            
            available = [g for g in groups if not g[4] and not group_blacklist.is_banned(g[0])]
            if not available:
                await asyncio.sleep(10)
                continue
            
            group = random.choice(available)
            group_id, group_name = group[0], group[1]
            
            try:
                message_text = encrypt_text(active_msg['content']) if SETTINGS.get('encryption') else active_msg['content']
                entity = await client.get_entity(int(group_id))
                await client.send_message(entity, message_text)
                db.log_post(phone, group_id, group_name, 'success')
                logger.success(f"✅ تم النشر في {group_name[:30]}")
            except Exception as e:
                db.log_post(phone, group_id, group_name, 'failed', str(e)[:100])
                group_blacklist.record_failure(group_id, str(e))
            
            interval = SETTINGS.get('interval', 5)
            if SETTINGS.get('anti_detection'):
                interval += random.uniform(1, 4)
            await asyncio.sleep(interval)
            
        except Exception as e:
            logger.error(f"💥 خطأ: {str(e)[:200]}")
            await asyncio.sleep(10)

# ==================== الدالة الرئيسية ====================

async def main():
    global bot, db, SETTINGS, start_time
    
    start_time = datetime.now()
    
    print("=" * 60)
    print("🤖 بوت النشر الخارق v5.0 - نسخة نظيفة")
    print(f"🗄️ نوع القاعدة: {'PostgreSQL خارجية' if DATABASE_URL else 'SQLite محلية'}")
    print("=" * 60)
    
    # 1. تشغيل Flask فوراً
    print(f"🌐 بدء Flask على المنفذ {PORT}...")
    web_thread = Thread(target=run_web, daemon=True)
    web_thread.start()
    await asyncio.sleep(1.5)
    print("✅ Flask متاح الآن")
    
    # 2. تهيئة قاعدة البيانات
    print("🗄️ تهيئة قاعدة البيانات...")
    db = Database()
    if DATABASE_URL:
        await db.init_postgres()
    SETTINGS.update(db.get_all_settings())
    
    # 3. إنشاء البوت
    bot = TelegramClient('bot_session', API_ID, API_HASH)
    bot.add_event_handler(start_handler, events.NewMessage(pattern='/start'))
    bot.add_event_handler(callback_handler, events.CallbackQuery())
    
    # 4. بدء البوت
    await bot.start(bot_token=BOT_TOKEN)
    bot_username = f"@{bot.me.username}" if bot.me else "جاهز"
    print(f"✅ البوت يعمل: {bot_username}")
    
    # 5. تحميل الحسابات
    for phone, status, _, _, _ in db.get_accounts():
        if status == 'active':
            session_str = db.get_account_session(phone)
            if session_str:
                try:
                    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
                    await client.start()
                    USER_CLIENTS[phone] = client
                    print(f"✅ حساب: {phone[-8:]}")
                except Exception as e:
                    print(f"❌ فشل حساب {phone[-8:]}: {e}")
    
    print("=" * 60)
    print(f"✅ جاهز! المنفذ: {PORT}")
    print(f"🤖 البوت: {bot_username}")
    print("=" * 60)
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 تم الإيقاف")
    except Exception as e:
        print(f"💥 خطأ: {e}")
