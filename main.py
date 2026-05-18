#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════╗
║     🤖 بوت النشر الخارق - مع Neon Cloud Database 🚀           ║
║     قاعدة بيانات سحابية 5GB مجاني + تشفير ذكي                ║
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

# ✅ قائمة المشرفين
ADMIN_IDS = [7853478744, 8603958200]

# ==================== إعدادات التشغيل ====================

DATA_DIR = "data"
BACKUPS_DIR = "backups"
LOGS_DIR = "logs"
DB_PATH = f"{DATA_DIR}/bot_data.db"

for dir_path in [DATA_DIR, BACKUPS_DIR, LOGS_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# ==================== قفل قاعدة البيانات المحلية ====================
db_lock = threading.Lock()

# ==================== خادم الويب ====================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({'status': 'online', 'msg': '🤖 البوت يعمل بنجاح!', 'time': str(datetime.now())})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

def run_web():
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

# ==================== قاعدة البيانات المحلية (احتياطي) ====================

class LocalDatabase:
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
            c.execute('''CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT, telegram_id TEXT, added_at TIMESTAMP)''')
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
        logger.success(f"✅ تم إضافة الحساب: {phone}")
    
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
    
    def get_account_session(self, phone):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            result = conn.execute('SELECT session_str FROM accounts WHERE phone = ?', (phone,)).fetchone()
            return result[0] if result else None
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
    
    def log_post(self, phone, group_id, group_name, status='success', error=None):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('INSERT INTO posting_history (phone, group_id, group_name, sent_at, status, error) VALUES (?, ?, ?, ?, ?, ?)', (phone, str(group_id), group_name[:50], datetime.now(), status, error))
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
    
    def create_backup(self):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"{BACKUPS_DIR}/backup_{timestamp}.db"
        with db_lock:
            shutil.copy2(self.db_path, backup_file)
        return backup_file
    
    def add_contact(self, name, phone, telegram_id=""):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('INSERT INTO contacts (name, phone, telegram_id, added_at) VALUES (?, ?, ?, ?)', (name, phone, telegram_id, datetime.now()))
                conn.commit()
            finally:
                conn.close()
    
    def get_contacts(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT id, name, phone, telegram_id, added_at FROM contacts ORDER BY added_at DESC').fetchall()
        finally:
            conn.close()

db_local = LocalDatabase()

# ==================== Neon Cloud Database (5GB مجاني) ====================

import asyncpg
import os

DATABASE_URL = os.environ.get('DATABASE_URL', '')

class NeonDatabase:
    def __init__(self):
        self.pool = None
        self.connected = False
        self._init_task = None
        if DATABASE_URL:
            try:
                # إنشاء اتصال غير متزامن
                self._init_task = asyncio.create_task(self._init())
            except Exception as e:
                logger.error(f"❌ فشل الاتصال بـ Neon: {e}")

    async def _init(self):
        try:
            self.pool = await asyncpg.create_pool(DATABASE_URL)
            self.connected = True
            logger.success("✅ تم الاتصال بـ Neon Cloud (5GB مجاني)")
            await self.init_tables()
        except Exception as e:
            logger.error(f"❌ فشل الاتصال بـ Neon: {e}")

    async def init_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    msg_id TEXT PRIMARY KEY,
                    content TEXT,
                    created_at TIMESTAMP,
                    is_active INTEGER DEFAULT 0
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    phone TEXT PRIMARY KEY,
                    session_str TEXT,
                    added_at TIMESTAMP,
                    last_active TIMESTAMP,
                    status TEXT,
                    total_posts INTEGER DEFAULT 0,
                    success_posts INTEGER DEFAULT 0,
                    failed_posts INTEGER DEFAULT 0
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS groups (
                    group_id TEXT PRIMARY KEY,
                    group_name TEXT,
                    group_username TEXT,
                    group_type TEXT,
                    members_count INTEGER DEFAULT 0,
                    added_by TEXT,
                    added_at TIMESTAMP,
                    last_post TIMESTAMP,
                    post_count INTEGER DEFAULT 0,
                    is_blacklisted INTEGER DEFAULT 0
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS posting_history (
                    id SERIAL PRIMARY KEY,
                    phone TEXT,
                    group_id TEXT,
                    group_name TEXT,
                    sent_at TIMESTAMP,
                    status TEXT,
                    error TEXT
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS joined_links (
                    id SERIAL PRIMARY KEY,
                    link TEXT,
                    group_id TEXT,
                    group_name TEXT,
                    joined_at TIMESTAMP,
                    joined_by TEXT
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS contacts (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    phone TEXT,
                    telegram_id TEXT,
                    added_at TIMESTAMP
                )
            ''')
            logger.success("✅ تم إنشاء الجداول في Neon")

    async def save_setting(self, key, value):
        if not self.connected:
            return db_local.save_setting(key, value)
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES ($1, $2, $3) "
                "ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = $3",
                key, json.dumps(value), datetime.now()
            )

    async def get_setting(self, key, default=None):
        if not self.connected:
            return db_local.get_setting(key, default)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT value FROM settings WHERE key = $1", key)
            if row:
                return json.loads(row['value'])
            return default

    async def get_all_settings(self):
        if not self.connected:
            return db_local.get_all_settings()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM settings")
            return {row['key']: json.loads(row['value']) for row in rows}

    async def save_message(self, msg_id, content, is_active=False):
        if not self.connected:
            return db_local.save_message(msg_id, content, is_active)
        async with self.pool.acquire() as conn:
            if is_active:
                await conn.execute("UPDATE messages SET is_active = 0")
            await conn.execute(
                "INSERT INTO messages (msg_id, content, created_at, is_active) VALUES ($1, $2, $3, $4) "
                "ON CONFLICT (msg_id) DO UPDATE SET content = $2, created_at = $3, is_active = $4",
                msg_id, content, datetime.now(), 1 if is_active else 0
            )

    async def get_all_messages(self):
        if not self.connected:
            return db_local.get_all_messages()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT msg_id, content, is_active FROM messages ORDER BY created_at DESC")
            return [(row['msg_id'], row['content'], row['is_active']) for row in rows]

    async def get_active_message(self):
        if not self.connected:
            return db_local.get_active_message()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT msg_id, content FROM messages WHERE is_active = 1")
            if row:
                return {'id': row['msg_id'], 'content': row['content']}
            row = await conn.fetchrow("SELECT msg_id, content FROM messages ORDER BY created_at DESC LIMIT 1")
            if row:
                await self.set_active_message(row['msg_id'])
                return {'id': row['msg_id'], 'content': row['content']}
            return None

    async def set_active_message(self, msg_id):
        if not self.connected:
            return db_local.set_active_message(msg_id)
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE messages SET is_active = 0")
            await conn.execute("UPDATE messages SET is_active = 1 WHERE msg_id = $1", msg_id)

    async def delete_message(self, msg_id):
        if not self.connected:
            return db_local.delete_message(msg_id)
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM messages WHERE msg_id = $1", msg_id)

    async def add_account(self, phone, session_str):
        if not self.connected:
            return db_local.add_account(phone, session_str)
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO accounts (phone, session_str, added_at, last_active, status) VALUES ($1, $2, $3, $4, $5) "
                "ON CONFLICT (phone) DO UPDATE SET session_str = $2, last_active = $4, status = $5",
                phone, session_str, datetime.now(), datetime.now(), 'active'
            )
        logger.success(f"✅ تم حفظ {phone} في Neon")

    async def get_accounts(self):
        if not self.connected:
            return db_local.get_accounts()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT phone, status, total_posts, success_posts, failed_posts FROM accounts ORDER BY added_at DESC")
            return [(row['phone'], row['status'], row['total_posts'], row['success_posts'], row['failed_posts']) for row in rows]

    async def remove_account(self, phone):
        if not self.connected:
            return db_local.remove_account(phone)
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM accounts WHERE phone = $1", phone)

    async def update_account_status(self, phone, status):
        if not self.connected:
            return db_local.update_account_status(phone, status)
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE accounts SET status = $1, last_active = $2 WHERE phone = $3", status, datetime.now(), phone)

    async def add_group(self, group_id, group_name, group_username, group_type, members_count, added_by):
        if not self.connected:
            return db_local.add_group(group_id, group_name, group_username, group_type, members_count, added_by)
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO groups (group_id, group_name, group_username, group_type, members_count, added_by, added_at) VALUES ($1, $2, $3, $4, $5, $6, $7) "
                "ON CONFLICT (group_id) DO NOTHING",
                str(group_id), group_name or "بدون اسم", group_username or "", group_type, members_count or 0, added_by, datetime.now()
            )

    async def get_all_groups(self):
        if not self.connected:
            return db_local.get_all_groups()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT group_id, group_name, members_count, post_count, is_blacklisted, last_post FROM groups ORDER BY post_count DESC")
            return [(row['group_id'], row['group_name'], row['members_count'], row['post_count'], row['is_blacklisted'], row['last_post']) for row in rows]

    async def get_blacklisted_groups(self):
        if not self.connected:
            return db_local.get_blacklisted_groups()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT group_id, group_name FROM groups WHERE is_blacklisted = 1")
            return [(row['group_id'], row['group_name']) for row in rows]

    async def log_post(self, phone, group_id, group_name, status='success', error=None):
        if not self.connected:
            return db_local.log_post(phone, group_id, group_name, status, error)
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO posting_history (phone, group_id, group_name, sent_at, status, error) VALUES ($1, $2, $3, $4, $5, $6)",
                phone, str(group_id), group_name[:50], datetime.now(), status, error
            )

    async def get_posting_stats(self, hours=24):
        if not self.connected:
            return db_local.get_posting_stats(hours)
        async with self.pool.acquire() as conn:
            since = datetime.now() - timedelta(hours=hours)
            total = await conn.fetchval("SELECT COUNT(*) FROM posting_history WHERE sent_at > $1", since)
            success = await conn.fetchval("SELECT COUNT(*) FROM posting_history WHERE sent_at > $1 AND status = 'success'", since)
            return {'total': total, 'success': success, 'failed': total - success}

    async def add_joined_link(self, link, group_id, group_name, joined_by):
        if not self.connected:
            return db_local.add_joined_link(link, group_id, group_name, joined_by)
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO joined_links (link, group_id, group_name, joined_at, joined_by) VALUES ($1, $2, $3, $4, $5)",
                link, str(group_id), group_name[:50], datetime.now(), joined_by
            )

    async def get_joined_links(self, limit=100):
        if not self.connected:
            return db_local.get_joined_links(limit)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT link, group_name, joined_at, joined_by FROM joined_links ORDER BY joined_at DESC LIMIT $1", limit)
            return [(row['link'], row['group_name'], row['joined_at'], row['joined_by']) for row in rows]

    async def add_contact(self, name, phone, telegram_id=""):
        if not self.connected:
            return db_local.add_contact(name, phone, telegram_id)
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO contacts (name, phone, telegram_id, added_at) VALUES ($1, $2, $3, $4)",
                name, phone, telegram_id, datetime.now()
            )

    async def get_contacts(self):
        if not self.connected:
            return db_local.get_contacts()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, name, phone, telegram_id, added_at FROM contacts ORDER BY added_at DESC")
            return [(row['id'], row['name'], row['phone'], row['telegram_id'], row['added_at']) for row in rows]

    async def create_backup(self):
        if not self.connected:
            return db_local.create_backup()
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f"{BACKUPS_DIR}/neon_backup_{timestamp}.json"
            
            async with self.pool.acquire() as conn:
                tables = ['settings', 'messages', 'accounts', 'groups', 'posting_history', 'joined_links', 'contacts']
                data = {}
                for table in tables:
                    rows = await conn.fetch(f"SELECT * FROM {table}")
                    data[table] = [dict(row) for row in rows]
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            
            logger.success(f"💾 تم إنشاء نسخة احتياطية من Neon: {backup_file}")
            return backup_file
        except Exception as e:
            logger.error(f"❌ فشل إنشاء النسخة الاحتياطية: {e}")
            return db_local.create_backup()

# ==================== اختيار قاعدة البيانات ====================

db_neon = NeonDatabase()

# دالة مساعدة للحصول على قاعدة البيانات المناسبة
def get_db():
    if db_neon.connected:
        return db_neon
    return db_local

db = get_db()

# ==================== المتغيرات العامة ====================

USER_CLIENTS = {}
SETTINGS = {
    'interval': 3, 
    'encryption': True, 
    'auto_join_enabled': True, 
    'save_joined_links': True
}
# نستخدم await للحصول على الإعدادات
# سنقوم بتهيئتها في main()

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
    enc_status = "✅ مفعل" if SETTINGS.get('encryption', True) else "❌ معطل"
    active_msg = asyncio.run_coroutine_threadsafe(db.get_active_message(), asyncio.get_event_loop()).result() if hasattr(db, 'get_active_message') else None
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
    return [
        [Button.inline(f"🤖 انضمام تلقائي {auto_join}", b"toggle_autojoin")],
        [Button.inline(f"💾 حفظ الروابط {save_links}", b"toggle_save_links")],
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

# ==================== المعالجات ====================

async def start_handler(event):
    if event.sender_id not in ADMIN_IDS:
        await event.respond("❌ غير مصرح لك باستخدام هذا البوت!")
        return
    
    accounts = await db.get_accounts()
    groups = await db.get_all_groups()
    joined_links = await db.get_joined_links_count() if hasattr(db, 'get_joined_links_count') else 0
    active_msg = await db.get_active_message()
    
    db_type = "☁️ Neon Cloud (5GB)" if db_neon.connected else "📁 محلية SQLite"
    
    await event.respond(
        f"👋 **أهلاً بك في بوت النشر الخارق!**\n\n"
        f"🗄️ **قاعدة البيانات:** {db_type}\n"
        f"🔐 **التشفير:** ذكي (يحافظ على الروابط)\n"
        f"📊 **الإحصائيات:**\n"
        f"• الحسابات: {len(accounts)}\n"
        f"• المجموعات: {len(groups)}\n"
        f"• المحظورات: {len(await db.get_blacklisted_groups())}\n"
        f"• الروابط المنضم لها: {joined_links}\n"
        f"• الرسائل المحفوظة: {len(await db.get_all_messages())}\n\n"
        f"📨 **الرسالة النشطة:**\n{active_msg['content'][:100] if active_msg else 'لا توجد'}\n\n"
        f"استخدم الأزرار للتحكم:", 
        buttons=main_buttons()
    )

async def callback_handler(event):
    global SETTINGS, is_posting
    
    if event.sender_id not in ADMIN_IDS:
        return
    
    data = event.data.decode()
    logger.info(f"🖱 نقرة: {data}")
    
    if data == "status":
        await show_status(event)
    elif data == "stats":
        await show_stats(event)
    elif data == "add":
        await event.edit("📱 أرسل رقم الهاتف مع رمز الدولة (مثال: +967...)"); 
        TEMP[event.sender_id] = {"state": "phone"}
    elif data == "del_list":
        await show_delete_list(event)
    elif data.startswith("rm_"):
        await delete_account(event, data.replace("rm_", ""))
    elif data == "time":
        await event.edit("⏱ أرسل الفاصل الزمني (1-60 ثانية):"); 
        TEMP[event.sender_id] = {"state": "time"}
    elif data == "toggle_enc":
        SETTINGS['encryption'] = not SETTINGS.get('encryption', True)
        await db.save_setting('encryption', SETTINGS['encryption'])
        await event.answer(f"✅ التشفير {'مفعل' if SETTINGS['encryption'] else 'معطل'}")
        await event.edit("👋 لوحة التحكم:", buttons=main_buttons())
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
        active = await db.get_active_message()
        if active:
            await event.answer(f"الرسالة النشطة: {active['content'][:50]}...", alert=True)
        else:
            await event.answer("❌ لا توجد رسالة نشطة", alert=True)
    
    elif data == "delete_database":
        await event.edit(
            "⚠️ **تحذير!** ⚠️\n\n"
            "أنت على وشك حذف قاعدة البيانات بالكامل!\n\n"
            "**سيتم إنشاء نسخة احتياطية**\n\n"
            "هل أنت متأكد؟",
            buttons=[
                [Button.inline("✅ نعم، احذف كل شيء", b"confirm_delete_db")],
                [Button.inline("❌ إلغاء", b"advanced")]
            ]
        )
    
    elif data == "confirm_delete_db":
        try:
            backup_file = await db.create_backup()
            logger.info(f"📦 تم إنشاء نسخة احتياطية: {backup_file}")
            
            for phone, client in USER_CLIENTS.items():
                try:
                    await client.disconnect()
                except:
                    pass
            USER_CLIENTS.clear()
            
            # حذف البيانات من قاعدة البيانات
            if db_neon.connected:
                async with db_neon.pool.acquire() as conn:
                    await conn.execute("TRUNCATE settings, messages, accounts, groups, posting_history, joined_links, contacts")
                logger.success("✅ تم إعادة تهيئة Neon")
            else:
                if os.path.exists(DB_PATH):
                    os.remove(DB_PATH)
                db_local.init_database()
            
            SETTINGS.update({
                'interval': 3,
                'encryption': True,
                'auto_join_enabled': True,
                'save_joined_links': True
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
        TEMP[event.sender_id] = {"state": "new_message"}
    elif data == "set_active_message":
        await show_set_active_message(event)
    elif data.startswith("set_active_"):
        msg_id = data.replace("set_active_", "")
        await db.set_active_message(msg_id)
        await event.answer("✅ تم تعيين الرسالة كنشطة", alert=True)
        await event.edit("📝 إدارة الرسائل", buttons=messages_buttons())
    elif data == "delete_message":
        await show_delete_message(event)
    elif data.startswith("del_msg_"):
        msg_id = data.replace("del_msg_", "")
        await db.delete_message(msg_id)
        await event.answer("✅ تم حذف الرسالة", alert=True)
        await event.edit("📝 إدارة الرسائل", buttons=messages_buttons())
    
    elif data == "toggle_autojoin":
        SETTINGS['auto_join_enabled'] = not SETTINGS.get('auto_join_enabled', True)
        await db.save_setting('auto_join_enabled', SETTINGS['auto_join_enabled'])
        await event.answer(f"✅ الانضمام التلقائي {'مفعل' if SETTINGS['auto_join_enabled'] else 'معطل'}")
        await event.edit("⚙️ الإعدادات المتقدمة:", buttons=advanced_buttons())
    elif data == "toggle_save_links":
        SETTINGS['save_joined_links'] = not SETTINGS.get('save_joined_links', True)
        await db.save_setting('save_joined_links', SETTINGS['save_joined_links'])
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
        TEMP[event.sender_id] = {"state": "add_blacklist"}
    elif data == "remove_blacklist":
        await show_remove_blacklist(event)
    elif data.startswith("unblack_"):
        await remove_from_blacklist(event, data.replace("unblack_", ""))
    elif data == "refresh_groups":
        await refresh_groups(event)
    elif data == "search_groups":
        await event.edit("🔍 أرسل كلمة البحث:")
        TEMP[event.sender_id] = {"state": "search_groups"}
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
        TEMP[event.sender_id] = {"state": "add_contact"}
    elif data == "list_contacts":
        await show_contacts_list(event)
    elif data == "delete_contact":
        await show_delete_contact(event)
    elif data == "message_contact":
        await show_message_contact(event)
    
    elif data == "start_p":
        if not USER_CLIENTS:
            return await event.answer("❌ لا توجد حسابات!", alert=True)
        active_msg = await db.get_active_message()
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

# ===== دوال العرض =====

async def list_all_messages(event):
    messages = await db.get_all_messages()
    if not messages:
        await event.edit("📭 لا توجد رسائل", buttons=messages_buttons())
        return
    
    text = "📋 **جميع الرسائل المحفوظة**\n\n"
    for i, (msg_id, content, is_active) in enumerate(messages[:15], 1):
        status = "🌟 نشطة" if is_active else "📄 عادية"
        preview = content[:50] + "..." if len(content) > 50 else content
        text += f"{i}. {status}\n   `{preview}`\n   🆔 {msg_id}\n\n"
    
    await event.edit(text, buttons=messages_buttons())

async def show_set_active_message(event):
    messages = await db.get_all_messages()
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
    messages = await db.get_all_messages()
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
    stats_24h = await db.get_posting_stats(24)
    stats_7d = await db.get_posting_stats(168)
    recent = await db.get_recent_posts(10) if hasattr(db, 'get_recent_posts') else []
    
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
    
    if recent:
        text += f"**آخر 10 عمليات:**\n"
        for phone, group, status, sent_at in recent[:10]:
            time_str = sent_at.strftime('%H:%M:%S') if isinstance(sent_at, datetime) else sent_at[:19]
            icon = "✅" if status == 'success' else "❌"
            text += f"{icon} {time_str} - {group[:25]}\n"
    
    await event.edit(text, buttons=reports_buttons())

async def show_accounts_report(event):
    accounts = await db.get_accounts()
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
    groups = await db.get_all_groups()
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
    links = await db.get_joined_links(50) if hasattr(db, 'get_joined_links') else []
    if not links:
        await event.edit("📭 لا توجد روابط", buttons=reports_buttons())
        return
    
    text = "🔗 **تقرير الروابط**\n\n"
    text += f"📊 إجمالي الروابط: {len(links)}\n\n"
    text += "**آخر 20 رابط:**\n"
    
    for link, group_name, joined_at, joined_by in links[:20]:
        time_str = joined_at.strftime('%Y-%m-%d %H:%M') if isinstance(joined_at, datetime) else joined_at[:16]
        text += f"• **{group_name[:30]}**\n"
        text += f"  🔗 {link[:40]}...\n"
        text += f"  📱 {joined_by[-8:]} | 🕐 {time_str}\n\n"
    
    await event.edit(text, buttons=reports_buttons())

async def show_status(event):
    accounts = await db.get_accounts()
    groups = await db.get_all_groups()
    blacklisted = await db.get_blacklisted_groups()
    stats = await db.get_posting_stats()
    joined_links = await db.get_joined_links_count() if hasattr(db, 'get_joined_links_count') else 0
    messages_count = len(await db.get_all_messages())
    active_msg = await db.get_active_message()
    uptime = datetime.now() - start_time
    hours = uptime.total_seconds() // 3600
    minutes = (uptime.total_seconds() % 3600) // 60
    
    active_accounts = len([a for a in accounts if a[1] == 'active'])
    contacts_count = len(await db.get_contacts()) if hasattr(db, 'get_contacts') else 0
    
    db_type = "☁️ Neon Cloud (5GB)" if db_neon.connected else "📁 محلية SQLite"
    
    text = f"📊 **حالة البوت**\n\n"
    text += f"🗄️ **قاعدة البيانات:** {db_type}\n"
    text += f"🔐 **التشفير:** ذكي (يحافظ على الروابط)\n"
    text += f"⏰ **وقت التشغيل:** {int(hours)} س {int(minutes)} د\n"
    text += f"👤 **الحسابات:** {active_accounts}/{len(accounts)}\n"
    text += f"📨 **المنشورات اليوم:** {stats['total']}\n"
    text += f"✅ **الناجح:** {stats['success']}\n"
    text += f"❌ **الفاشل:** {stats['failed']}\n"
    text += f"📢 **المجموعات:** {len(groups)}\n"
    text += f"🚫 **المحظورات:** {len(blacklisted)}\n"
    text += f"🔗 **الروابط:** {joined_links}\n"
    text += f"📝 **الرسائل:** {messages_count}\n"
    text += f"📞 **جهات الاتصال:** {contacts_count}\n"
    text += f"⚙️ **الفاصل:** {SETTINGS['interval']} ثانية\n"
    text += f"🚫 **محظورات مؤقتة:** {group_blacklist.get_banned_count()}\n"
    text += f"🔄 **النشر:** {'🟢 نشط' if is_posting else '🔴 متوقف'}\n"
    
    if active_msg:
        text += f"\n📨 **الرسالة النشطة:**\n{active_msg['content'][:100]}..."
    
    await event.edit(text, buttons=main_buttons())

async def show_stats(event):
    stats = await db.get_posting_stats()
    recent = await db.get_recent_posts(5) if hasattr(db, 'get_recent_posts') else []
    
    text = f"📈 **إحصائيات آخر 24 ساعة**\n\n"
    text += f"📊 الإجمالي: {stats['total']}\n"
    text += f"✅ الناجح: {stats['success']}\n"
    text += f"❌ الفاشل: {stats['failed']}\n"
    text += f"📊 نسبة النجاح: {stats['success']/(stats['total'] or 1)*100:.1f}%\n\n"
    
    if recent:
        text += f"📋 آخر النشاطات:\n"
        for phone, group, status, sent_at in recent[:5]:
            time_str = sent_at.strftime('%H:%M') if isinstance(sent_at, datetime) else sent_at[:5]
            icon = "✅" if status == 'success' else "❌"
            text += f"{icon} {time_str} - {group[:20]}\n"
    
    await event.edit(text, buttons=main_buttons())

async def show_detailed_stats(event):
    accounts = await db.get_accounts()
    groups = await db.get_all_groups()
    joined_links = await db.get_joined_links_count() if hasattr(db, 'get_joined_links_count') else 0
    
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
    recent = await db.get_recent_posts(15) if hasattr(db, 'get_recent_posts') else []
    text = "📋 **آخر 15 عملية نشر**\n\n"
    
    for phone, group, status, sent_at in recent:
        time_str = sent_at.strftime('%H:%M:%S') if isinstance(sent_at, datetime) else sent_at[:19]
        icon = "✅" if status == 'success' else "❌"
        text += f"{icon} {time_str} - {group[:20]}\n"
    
    await event.edit(text, buttons=advanced_buttons())

async def show_delete_list(event):
    accounts = await db.get_accounts()
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
    groups = await db.get_all_groups()
    blacklisted = await db.get_blacklisted_groups()
    
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
    blacklisted = await db.get_blacklisted_groups()
    if not blacklisted:
        await event.edit("📭 لا توجد مجموعات محظورة", buttons=blacklist_buttons())
        return
    
    text = "🚫 **المجموعات المحظورة**\n\n"
    for gid, name in blacklisted[:20]:
        text += f"• {name[:40]}\n"
        text += f"  🆔 {gid}\n\n"
    
    await event.edit(text, buttons=blacklist_buttons())

async def show_remove_blacklist(event):
    blacklisted = await db.get_blacklisted_groups()
    if not blacklisted:
        return await event.answer("❌ لا توجد محظورات", alert=True)
    
    btns = []
    for gid, name in blacklisted[:10]:
        btns.append([Button.inline(f"✅ {name[:20]}", f"unblack_{gid}".encode())])
    
    btns.append([Button.inline("⬅️ عودة", b"blacklist_menu")])
    await event.edit("✅ اختر مجموعة للإزالة", buttons=btns)

async def show_group_stats(event):
    groups = await db.get_all_groups()
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
    links = await db.get_joined_links(20) if hasattr(db, 'get_joined_links') else []
    if not links:
        await event.edit("📭 لا توجد روابط\n\nأرسل روابط المجموعات للانضمام.", buttons=main_buttons())
        return
    
    text = "🔗 **آخر 20 رابط تم الانضمام لها**\n\n"
    for link, group_name, joined_at, joined_by in links:
        time_str = joined_at.strftime('%Y-%m-%d %H:%M') if isinstance(joined_at, datetime) else joined_at[:16]
        text += f"• **{group_name[:30]}**\n"
        text += f"  🔗 {link[:40]}...\n"
        text += f"  📱 {joined_by[-8:]} | 🕐 {time_str}\n\n"
    
    await event.edit(text, buttons=main_buttons())

# ===== دوال جهات الاتصال =====

async def show_contacts_list(event):
    contacts = await db.get_contacts() if hasattr(db, 'get_contacts') else []
    if not contacts:
        await event.edit("📭 **لا توجد جهات اتصال**\n\nاستخدم زر '➕ إضافة جهة اتصال' لإضافة جهة جديدة.", 
                        buttons=contacts_buttons())
        return
    
    text = "📞 **جهات الاتصال**\n\n"
    for i, (cid, name, phone, tg_id, added_at) in enumerate(contacts[:20], 1):
        added_time = added_at.strftime('%Y-%m-%d') if isinstance(added_at, datetime) else added_at[:10]
        text += f"{i}. **{name}**\n"
        text += f"   📱 {phone}\n"
        if tg_id:
            text += f"   🆔 {tg_id}\n"
        text += f"   🕐 {added_time}\n\n"
    
    if len(contacts) > 20:
        text += f"\n... و {len(contacts) - 20} جهة أخرى"
    
    await event.edit(text, buttons=contacts_buttons())

async def show_delete_contact(event):
    contacts = await db.get_contacts() if hasattr(db, 'get_contacts') else []
    if not contacts:
        await event.answer("❌ لا توجد جهات اتصال!", alert=True)
        return
    
    btns = []
    for cid, name, phone, tg_id, added_at in contacts[:10]:
        btns.append([Button.inline(f"🗑 {name[:20]}", f"del_contact_{cid}".encode())])
    
    btns.append([Button.inline("⬅️ عودة", b"contacts_menu")])
    await event.edit("🗑 **اختر جهة اتصال للحذف:**", buttons=btns)

async def show_message_contact(event):
    contacts = await db.get_contacts() if hasattr(db, 'get_contacts') else []
    if not contacts:
        await event.answer("❌ لا توجد جهات اتصال!", alert=True)
        return
    
    btns = []
    for cid, name, phone, tg_id, added_at in contacts[:10]:
        btns.append([Button.inline(f"📨 {name[:20]}", f"msg_contact_{cid}".encode())])
    
    btns.append([Button.inline("⬅️ عودة", b"contacts_menu")])
    await event.edit("📨 **اختر جهة اتصال لإرسال رسالة:**\n\nسيتم إرسال آخر رسالة نشطة إلى جهة الاتصال.", buttons=btns)

# ===== دوال الإجراءات =====

async def delete_account(event, phone):
    if phone in USER_CLIENTS:
        try:
            await USER_CLIENTS[phone].disconnect()
        except:
            pass
        del USER_CLIENTS[phone]
    await db.remove_account(phone)
    await event.answer(f"✅ تم حذف {phone}", alert=True)
    await show_delete_list(event)

async def remove_from_blacklist(event, group_id):
    await db.whitelist_group(group_id)
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
                    await db.add_group(dialog.id, dialog.name, getattr(dialog.entity, 'username', None), 
                                'group', members, phone)
                    count += 1
        except:
            pass
    await event.answer(f"✅ تم تحديث {count} مجموعة")
    await event.edit("🗂 إدارة المجموعات:", buttons=groups_buttons())

async def create_backup_handler(event):
    try:
        backup_file = await db.create_backup()
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
                    await db.add_group(dialog.id, dialog.name, getattr(dialog.entity, 'username', None), 
                                'group', members, phone)
                    count += 1
        except:
            pass
    logger.info(f"✅ تم تحديث {count} مجموعة")

# ===== معالج النصوص =====

async def text_handler(event):
    user_id = event.sender_id
    if user_id not in ADMIN_IDS:
        return
    
    state = TEMP.get(user_id)
    text = event.message.text.strip()
    
    if state and state.get("state") == "new_message":
        msg_id = f"msg_{int(time.time())}"
        await db.save_message(msg_id, text, is_active=False)
        TEMP.pop(user_id, None)
        await event.respond(f"✅ **تم إضافة الرسالة!**", buttons=messages_buttons())
        return
    
    elif state and state.get("state") == "phone":
        await handle_phone_login(event, text, user_id)
        return
    
    elif state and state.get("state") == "code":
        await handle_code_verification(event, state, text, user_id)
        return
    
    elif state and state.get("state") == "password":
        await handle_password(event, state, text, user_id)
        return
    
    elif state and state.get("state") == "time":
        try:
            interval = int(text)
            if 1 <= interval <= 60:
                SETTINGS['interval'] = interval
                await db.save_setting('interval', interval)
                TEMP.pop(user_id, None)
                await event.respond(f"✅ تم ضبط الوقت على {text} ثانية", buttons=main_buttons())
            else:
                await event.respond("❌ الرجاء إدخال قيمة بين 1 و 60")
        except:
            await event.respond("❌ أرسل رقماً فقط")
        return
    
    elif state and state.get("state") == "add_blacklist":
        groups = await db.search_groups(text) if hasattr(db, 'search_groups') else []
        if groups:
            for gid, name, members in groups[:5]:
                await db.blacklist_group(gid)
            await event.respond(f"✅ تم حظر {len(groups[:5])} مجموعة")
        else:
            await event.respond("❌ لم يتم العثور على مجموعات")
        TEMP.pop(user_id, None)
        await event.respond("⚙️ الإعدادات المتقدمة:", buttons=advanced_buttons())
        return
    
    elif state and state.get("state") == "search_groups":
        groups = await db.search_groups(text) if hasattr(db, 'search_groups') else []
        if groups:
            msg = f"🔍 **نتائج البحث:**\n\n"
            for gid, name, members in groups:
                msg += f"• {name[:40]}\n  👥 {format_number(members)}\n"
            await event.respond(msg)
        else:
            await event.respond("❌ لا توجد نتائج")
        TEMP.pop(user_id, None)
        return
    
    elif state and state.get("state") == "add_contact":
        parts = text.rsplit(' ', 1)
        if len(parts) == 2:
            name = parts[0]
            phone = parts[1]
            await db.add_contact(name, phone)
            await event.respond(f"✅ **تم إضافة جهة الاتصال:**\n📞 {name}\n📱 {phone}")
        else:
            await event.respond("❌ **صيغة غير صحيحة!**\nأرسل الاسم ثم رقم الهاتف\nمثال: أحمد +967712345678")
        TEMP.pop(user_id, None)
        await event.respond("📞 قائمة جهات الاتصال:", buttons=contacts_buttons())
        return
    
    else:
        links = re.findall(r"(https?://t\.me/(?:joinchat/|\+)[a-zA-Z0-9_-]+|https?://t\.me/[a-zA-Z0-9_]+)", text)
        if links and SETTINGS.get('auto_join_enabled', True) and USER_CLIENTS:
            await handle_auto_join_slow(event, links)

# ===== دوال تسجيل الدخول =====

async def handle_phone_login(event, phone, user_id):
    try:
        if not phone.startswith('+'):
            phone = '+' + phone
        
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        await client.send_code_request(phone)
        
        TEMP[user_id] = {
            "state": "code",
            "phone": phone,
            "client": client
        }
        
        await event.respond(f"📩 **تم إرسال كود التحقق** إلى {phone}\n\nأرسل الكود:")
        logger.info(f"📱 تم إرسال كود التحقق إلى {phone}")
        
    except Exception as e:
        await event.respond(f"❌ **خطأ:** {str(e)[:200]}")

async def handle_code_verification(event, state, code, user_id):
    try:
        client = state["client"]
        phone = state["phone"]
        
        await client.sign_in(phone, code)
        
        session_str = client.session.save()
        await db.add_account(phone, session_str)
        USER_CLIENTS[phone] = client
        
        TEMP.pop(user_id, None)
        
        await event.respond(f"✅ **تم تفعيل الحساب بنجاح!**\n\n📱 {phone}")
        logger.success(f"✅ تم تسجيل الدخول بنجاح: {phone}")
        
        asyncio.create_task(refresh_groups_async())
        
    except SessionPasswordNeededError:
        TEMP[user_id] = {
            "state": "password",
            "phone": phone,
            "client": client
        }
        await event.respond("🔐 **يتطلب الحساب كلمة مرور** (2FA)\n\nأرسل كلمة المرور:")
    except Exception as e:
        await event.respond(f"❌ **فشل التحقق:** {str(e)[:200]}")
        TEMP.pop(user_id, None)

async def handle_password(event, state, password, user_id):
    try:
        client = state["client"]
        phone = state["phone"]
        
        await client.sign_in(password=password)
        
        session_str = client.session.save()
        await db.add_account(phone, session_str)
        USER_CLIENTS[phone] = client
        
        TEMP.pop(user_id, None)
        
        await event.respond(f"✅ **تم تفعيل الحساب بنجاح!**\n\n📱 {phone}")
        logger.success(f"✅ تم تسجيل الدخول (2FA): {phone}")
        
        asyncio.create_task(refresh_groups_async())
        
    except Exception as e:
        await event.respond(f"❌ **كلمة مرور غير صحيحة!**")

# ===== دالة الانضمام البطيء =====

async def handle_auto_join_slow(event, links):
    max_links = min(len(links), 5)
    
    await event.respond(
        f"🐢 **انضمام بطيء لـ {max_links} رابط**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 عدد الروابط: {max_links}\n"
        f"⏱ الوقت المتوقع: {max_links * 2}-{max_links * 4} دقائق\n"
        f"🛡 هذا الإعداد يحمي الحسابات من الحظر\n\n"
        f"جاري البدء..."
    )
    
    success = 0
    failed = 0
    saved = 0
    
    for i, link in enumerate(links[:max_links]):
        if i > 0:
            delay = random.randint(30, 60)
            logger.info(f"⏸ انتظار {delay} ثانية...")
            await asyncio.sleep(delay)
        
        joined = False
        for phone, client in USER_CLIENTS.items():
            if joined:
                break
                
            try:
                pre_delay = random.randint(15, 30)
                await asyncio.sleep(pre_delay)
                
                group_info = None
                if "joinchat" in link or "+" in link:
                    hash_part = link.split('/')[-1].replace('+', '')
                    updates = await client(ImportChatInviteRequest(hash_part))
                    if updates.chats:
                        chat = updates.chats[0]
                        group_info = (chat.id, chat.title)
                else:
                    username = link.split('/')[-1]
                    entity = await client.get_entity(username)
                    if entity:
                        await client(JoinChannelRequest(link))
                        group_info = (entity.id, getattr(entity, 'title', username))
                
                success += 1
                joined = True
                logger.success(f"✅ تم الانضمام بنجاح")
                
                post_delay = random.randint(20, 40)
                await asyncio.sleep(post_delay)
                
                if SETTINGS.get('save_joined_links', True) and group_info:
                    group_id, group_name = group_info
                    await db.add_joined_link(link, group_id, group_name[:50], phone)
                    saved += 1
                
                break
                
            except FloodWaitError as e:
                wait_time = e.seconds + random.randint(15, 30)
                logger.warning(f"⏳ FloodWait: انتظار {wait_time} ثانية...")
                await asyncio.sleep(wait_time)
                continue
            except Exception as e:
                failed += 1
                logger.error(f"❌ فشل الانضمام: {e}")
                await asyncio.sleep(random.randint(30, 60))
                continue
        
        if not joined:
            failed += 1
            await asyncio.sleep(random.randint(45, 75))
    
    result_text = f"📊 **نتيجة الانضمام:**\n"
    result_text += f"━━━━━━━━━━━━━━━━━━━━\n"
    result_text += f"✅ نجاح: {success}\n"
    result_text += f"❌ فشل: {failed}\n"
    if saved > 0:
        result_text += f"\n💾 تم حفظ: {saved} رابط"
    
    await event.respond(result_text)

# ===== دالة النشر =====

async def poster():
    global is_posting
    logger.info("🚀 بدء النشر...")
    
    while is_posting:
        try:
            if not USER_CLIENTS:
                await asyncio.sleep(5)
                continue
            
            active_msg = await db.get_active_message()
            if not active_msg:
                logger.warning("⚠️ لا توجد رسالة نشطة")
                await asyncio.sleep(5)
                continue
            
            txt = active_msg['content']
            
            for phone, client in list(USER_CLIENTS.items()):
                if not is_posting:
                    break
                
                try:
                    async for dialog in client.iter_dialogs():
                        if not is_posting:
                            break
                        
                        if dialog.is_group:
                            blacklisted = [g[0] for g in await db.get_blacklisted_groups()]
                            if str(dialog.id) in blacklisted:
                                continue
                            
                            if group_blacklist.is_banned(str(dialog.id)):
                                continue
                            
                            try:
                                await db.add_group(dialog.id, dialog.name, 
                                            getattr(dialog.entity, 'username', None), 
                                            'group', 
                                            getattr(dialog.entity, 'participants_count', 0), 
                                            phone)
                                
                                # ✅ استخدام التشفير الذكي
                                encrypted_text = SmartEncryption.encrypt(txt)
                                await client.send_message(dialog.id, encrypted_text)
                                
                                await db.log_post(phone, dialog.id, dialog.name, 'success')
                                group_blacklist.clear_banned(str(dialog.id))
                                await asyncio.sleep(SETTINGS['interval'])
                                
                            except FloodWaitError as e:
                                logger.warning(f"FloodWait: {e.seconds} ثانية")
                                await asyncio.sleep(e.seconds)
                            except Exception as e:
                                error_msg = str(e)[:100]
                                await db.log_post(phone, dialog.id, dialog.name, 'failed', error_msg)
                                if "banned" in error_msg.lower() or "can't write" in error_msg.lower():
                                    group_blacklist.record_failure(str(dialog.id), error_msg)
                                
                except Exception as e:
                    logger.error(f"خطأ في الحساب {phone}: {e}")
                    
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"خطأ في النشر: {e}")
            await asyncio.sleep(10)

# ===== استعادة الجلسات =====

async def restore_sessions():
    restored = 0
    accounts = await db.get_accounts()
    logger.info(f"🔍 استعادة {len(accounts)} حساب...")
    
    for account in accounts:
        try:
            phone = account[0]
            session_str = None
            if db_neon.connected:
                async with db_neon.pool.acquire() as conn:
                    row = await conn.fetchrow("SELECT session_str FROM accounts WHERE phone = $1", phone)
                    if row:
                        session_str = row['session_str']
            else:
                session_str = db_local.get_account_session(phone)
            
            if not session_str:
                continue
            
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.connect()
            
            if await client.is_user_authorized():
                USER_CLIENTS[phone] = client
                await db.update_account_status(phone, 'active')
                restored += 1
                logger.success(f"✅ تم استعادة {phone}")
            else:
                await db.update_account_status(phone, 'unauthorized')
        except Exception as e:
            logger.error(f"❌ فشل استعادة: {e}")
    
    logger.info(f"✅ تم استعادة {restored} حساب")
    return restored

# ===== التشغيل الرئيسي =====

async def main():
    global bot, start_time, SETTINGS
    start_time = datetime.now()
    
    # تشغيل خادم الويب
    Thread(target=run_web, daemon=True).start()
    
    # انتظار اكتمال اتصال Neon
    if db_neon._init_task:
        await db_neon._init_task
    
    # تحميل الإعدادات
    try:
        loaded_settings = await db.get_all_settings()
        if loaded_settings:
            SETTINGS.update(loaded_settings)
        logger.success("✅ تم تحميل الإعدادات")
    except Exception as e:
        logger.warning(f"⚠️ فشل تحميل الإعدادات: {e}")
    
    print("\n" + "="*60)
    print("🚀 جاري تشغيل البوت...")
    print("="*60)
    print(f"👤 المشرفون: {ADMIN_IDS}")
    print(f"🗄️ قاعدة البيانات: {'Neon Cloud (5GB)' if db_neon.connected else 'SQLite محلية'}")
    print(f"🔐 نظام التشفير: ذكي (يحافظ على الروابط واليوزرات)")
    print(f"📞 نظام جهات الاتصال: مفعل")
    print("="*60 + "\n")
    
    await restore_sessions()
    
    bot = TelegramClient('bot_session', API_ID, API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    
    me = await bot.get_me()
    print(f"✅ البوت متصل: @{me.username}")
    print(f"👤 آيدي البوت: {me.id}")
    print(f"📱 رابط البوت: t.me/{me.username}")
    print("\n" + "="*60)
    print("🎉 البوت جاهز! أرسل /start")
    print("="*60 + "\n")
    
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_handler_event(e):
        print(f"📩 استقبلت أمر /start من {e.sender_id}")
        await start_handler(e)
    
    @bot.on(events.CallbackQuery())
    async def callback_handler_event(e):
        print(f"🖱 استقبلت ضغطة زر من {e.sender_id}")
        await callback_handler(e)
    
    @bot.on(events.NewMessage)
    async def text_handler_event(e):
        if e.message.text and e.sender_id in ADMIN_IDS:
            print(f"💬 استقبلت رسالة من مشرف: {e.message.text[:50]}...")
            await text_handler(e)
    
    logger.success("✅ البوت يعمل بنجاح!")
    
    await bot.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 تم إيقاف البوت")
    except Exception as e:
        logger.critical(f"💥 خطأ: {e}")
        print("🔄 إعادة التشغيل...")
        time.sleep(5)
        os.execl(sys.executable, sys.executable, *sys.argv)
