#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════╗
║     🤖 بوت النشر الخارق - نسخة نظيفة تماماً 🚀              ║
║     بدون قفل - بدون فحص قنوات - بدون اشتراكات               ║
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

# ==================== إعدادات التشغيل ====================

DATA_DIR = "data"
BACKUPS_DIR = "backups"
LOGS_DIR = "logs"
DB_PATH = f"{DATA_DIR}/bot_data.db"

for dir_path in [DATA_DIR, BACKUPS_DIR, LOGS_DIR]:
    os.makedirs(dir_path, exist_ok=True)

db_lock = threading.Lock()

# ==================== خادم الويب ====================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({'status': 'online', 'msg': '🤖 Bot Running!', 'time': str(datetime.now())})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

def run_web():
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Flask on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ==================== نظام التسجيل ====================

class Logger:
    def __init__(self):
        log_file = f"{LOGS_DIR}/bot_{datetime.now().strftime('%Y%m%d')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(log_file, encoding='utf-8'), logging.StreamHandler()]
        )
        self.logger = logging.getLogger('Bot')
    
    def info(self, msg): self.logger.info(msg); print(f"ℹ️ {msg}")
    def error(self, msg): self.logger.error(msg); print(f"❌ {msg}")
    def success(self, msg): self.logger.info(f"✅ {msg}"); print(f"✅ {msg}")

logger = Logger()

# ==================== قاعدة بيانات بسيطة ====================

class SimpleDB:
    def __init__(self):
        self.db_path = DB_PATH
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS messages (msg_id TEXT PRIMARY KEY, content TEXT, is_active INTEGER DEFAULT 0)''')
            c.execute('''CREATE TABLE IF NOT EXISTS accounts (phone TEXT PRIMARY KEY, session_str TEXT, status TEXT DEFAULT 'active')''')
            c.execute('''CREATE TABLE IF NOT EXISTS groups (group_id TEXT PRIMARY KEY, group_name TEXT, members_count INTEGER DEFAULT 0, post_count INTEGER DEFAULT 0, is_blacklisted INTEGER DEFAULT 0)''')
            c.execute('''CREATE TABLE IF NOT EXISTS posting_history (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, group_name TEXT, status TEXT, sent_at TIMESTAMP)''')
            c.execute('''CREATE TABLE IF NOT EXISTS joined_links (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, group_name TEXT, joined_at TIMESTAMP)''')
            c.execute('''CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT)''')
            conn.commit()
            conn.close()
        logger.success("✅ Database ready")
        
        if not self.get_all_messages():
            self.save_message("default", "📢 Welcome to the bot!\n\nThis is a test message.", is_active=True)
    
    def save_setting(self, key, value):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', (key, json.dumps(value)))
            conn.commit()
            conn.close()
    
    def get_setting(self, key, default=None):
        conn = sqlite3.connect(self.db_path, timeout=15)
        result = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
        conn.close()
        return json.loads(result[0]) if result else default
    
    def save_message(self, msg_id, content, is_active=False):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            if is_active:
                conn.execute('UPDATE messages SET is_active = 0')
            conn.execute('INSERT OR REPLACE INTO messages VALUES (?, ?, ?)', (msg_id, content, 1 if is_active else 0))
            conn.commit()
            conn.close()
    
    def get_all_messages(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        rows = conn.execute('SELECT msg_id, content, is_active FROM messages ORDER BY msg_id DESC').fetchall()
        conn.close()
        return rows
    
    def get_active_message(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        row = conn.execute('SELECT msg_id, content FROM messages WHERE is_active = 1').fetchone()
        conn.close()
        if row:
            return {'id': row[0], 'content': row[1]}
        return None
    
    def set_active_message(self, msg_id):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.execute('UPDATE messages SET is_active = 0')
            conn.execute('UPDATE messages SET is_active = 1 WHERE msg_id = ?', (msg_id,))
            conn.commit()
            conn.close()
    
    def delete_message(self, msg_id):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.execute('DELETE FROM messages WHERE msg_id = ?', (msg_id,))
            conn.commit()
            conn.close()
    
    def add_account(self, phone, session_str):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.execute('INSERT OR REPLACE INTO accounts VALUES (?, ?, ?)', (phone, session_str, 'active'))
            conn.commit()
            conn.close()
        logger.success(f"✅ Account added: {phone}")
    
    def remove_account(self, phone):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.execute('DELETE FROM accounts WHERE phone = ?', (phone,))
            conn.commit()
            conn.close()
    
    def get_accounts(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        rows = conn.execute('SELECT phone, status FROM accounts ORDER BY phone DESC').fetchall()
        conn.close()
        return [(r[0], r[1], 0, 0, 0) for r in rows]
    
    def get_account_session(self, phone):
        conn = sqlite3.connect(self.db_path, timeout=15)
        result = conn.execute('SELECT session_str FROM accounts WHERE phone = ?', (phone,)).fetchone()
        conn.close()
        return result[0] if result else None
    
    def add_group(self, group_id, group_name, group_username, group_type, members_count, added_by):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.execute('INSERT OR IGNORE INTO groups (group_id, group_name, members_count) VALUES (?, ?, ?)', 
                        (str(group_id), group_name or "Unknown", members_count or 0))
            conn.commit()
            conn.close()
    
    def get_all_groups(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        rows = conn.execute('SELECT group_id, group_name, members_count, post_count, is_blacklisted, NULL FROM groups ORDER BY post_count DESC').fetchall()
        conn.close()
        return rows
    
    def get_blacklisted_groups(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        rows = conn.execute('SELECT group_id, group_name FROM groups WHERE is_blacklisted = 1').fetchall()
        conn.close()
        return rows
    
    def log_post(self, phone, group_id, group_name, status='success', error=None):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.execute('INSERT INTO posting_history (phone, group_name, status, sent_at) VALUES (?, ?, ?, ?)', 
                        (phone, group_name[:50], status, datetime.now()))
            conn.commit()
            conn.close()
    
    def get_posting_stats(self, hours=24):
        since = datetime.now() - timedelta(hours=hours)
        conn = sqlite3.connect(self.db_path, timeout=15)
        total = conn.execute('SELECT COUNT(*) FROM posting_history WHERE sent_at > ?', (since,)).fetchone()[0]
        success = conn.execute("SELECT COUNT(*) FROM posting_history WHERE sent_at > ? AND status = 'success'", (since,)).fetchone()[0]
        conn.close()
        return {'total': total, 'success': success, 'failed': total - success}
    
    def add_joined_link(self, link, group_id, group_name, joined_by):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.execute('INSERT INTO joined_links (link, group_name, joined_at) VALUES (?, ?, ?)', 
                        (link, group_name[:50], datetime.now()))
            conn.commit()
            conn.close()
    
    def get_joined_links(self, limit=100):
        conn = sqlite3.connect(self.db_path, timeout=15)
        rows = conn.execute('SELECT link, group_name, joined_at, ? FROM joined_links ORDER BY joined_at DESC LIMIT ?', ('', limit)).fetchall()
        conn.close()
        return [(r[0], r[1], r[2], '') for r in rows]
    
    def get_joined_links_count(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        count = conn.execute('SELECT COUNT(*) FROM joined_links').fetchone()[0]
        conn.close()
        return count
    
    def add_contact(self, name, phone, telegram_id=""):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.execute('INSERT INTO contacts (name, phone) VALUES (?, ?)', (name, phone))
            conn.commit()
            conn.close()
    
    def get_contacts(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        rows = conn.execute('SELECT id, name, phone, ?, ? FROM contacts ORDER BY id DESC').fetchall()
        conn.close()
        return [(r[0], r[1], r[2], '', '') for r in rows]
    
    def delete_contact(self, contact_id):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.execute('DELETE FROM contacts WHERE id = ?', (contact_id,))
            conn.commit()
            conn.close()

db = SimpleDB()

# ==================== المتغيرات العامة ====================

USER_CLIENTS = {}
SETTINGS = {'interval': 5, 'encryption': True}
is_posting = False
bot = None
start_time = datetime.now()

# ==================== الأزرار ====================

def main_buttons():
    return [
        [Button.inline("➕ Add Account", b"add"), Button.inline("🗑 Delete Account", b"del_list")],
        [Button.inline("📝 Messages", b"manage_messages"), Button.inline("⏱ Set Interval", b"time")],
        [Button.inline("🚀 Start Posting", b"start_p"), Button.inline("🛑 Stop Posting", b"stop_p")],
        [Button.inline("📊 Status", b"status"), Button.inline("📢 Groups", b"view_chats")],
        [Button.inline("🔗 Links", b"view_joined_links"), Button.inline("📞 Contacts", b"contacts_menu")]
    ]

def messages_buttons():
    return [
        [Button.inline("📋 List All", b"list_messages")],
        [Button.inline("➕ Add New", b"add_message")],
        [Button.inline("✅ Set Active", b"set_active_message")],
        [Button.inline("🗑 Delete", b"delete_message")],
        [Button.inline("⬅️ Back", b"back")]
    ]

def contacts_buttons():
    return [
        [Button.inline("➕ Add Contact", b"add_contact")],
        [Button.inline("📋 List Contacts", b"list_contacts")],
        [Button.inline("⬅️ Back", b"back")]
    ]

# ==================== معالج البداية - نظيف تماماً ====================

async def start_handler(event):
    """معالج أمر /start - بدون أي قفل أو فحص"""
    if event.sender_id != ADMIN_ID:
        await event.respond("❌ You are not authorized to use this bot!")
        return
    
    accounts = db.get_accounts()
    groups = db.get_all_groups()
    active_msg = db.get_active_message()
    
    await event.respond(
        f"👋 **Welcome to the Bot!**\n\n"
        f"📊 **Stats:**\n"
        f"• Accounts: {len(accounts)}\n"
        f"• Groups: {len(groups)}\n"
        f"• Messages: {len(db.get_all_messages())}\n\n"
        f"📨 **Active Message:**\n{active_msg['content'][:100] if active_msg else 'None'}\n\n"
        f"Use buttons below:", 
        buttons=main_buttons()
    )

async def callback_handler(event):
    global SETTINGS, is_posting
    
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Unauthorized!", alert=True)
        return
    
    data = event.data.decode()
    
    if data == "back":
        await event.edit("👋 Main Menu", buttons=main_buttons())
    elif data == "status":
        accounts = db.get_accounts()
        groups = db.get_all_groups()
        stats = db.get_posting_stats()
        text = f"📊 **Status**\n\nAccounts: {len(accounts)}\nGroups: {len(groups)}\nPosts today: {stats['total']}\nPosting: {'🟢 Active' if is_posting else '🔴 Stopped'}"
        await event.edit(text, buttons=main_buttons())
    elif data == "add":
        await event.edit("📱 Send phone number with country code:")
        TEMP[ADMIN_ID] = "phone"
    elif data == "del_list":
        accounts = db.get_accounts()
        if not accounts:
            await event.answer("No accounts!", alert=True)
            return
        btns = []
        for phone, status, _, _, _ in accounts[:10]:
            btns.append([Button.inline(f"🗑 {phone[-8:]}", f"rm_{phone}".encode())])
        btns.append([Button.inline("⬅️ Back", b"back")])
        await event.edit("Select account to delete:", buttons=btns)
    elif data.startswith("rm_"):
        phone = data.replace("rm_", "")
        if phone in USER_CLIENTS:
            try: await USER_CLIENTS[phone].disconnect()
            except: pass
            del USER_CLIENTS[phone]
        db.remove_account(phone)
        await event.answer(f"Deleted {phone}", alert=True)
        await event.edit("👋 Main Menu", buttons=main_buttons())
    elif data == "time":
        await event.edit("⏱ Send interval in seconds (1-60):")
        TEMP[ADMIN_ID] = "time"
    elif data == "manage_messages":
        await event.edit("📝 **Messages**", buttons=messages_buttons())
    elif data == "list_messages":
        messages = db.get_all_messages()
        if not messages:
            await event.edit("No messages", buttons=messages_buttons())
            return
        text = "📋 **All Messages**\n\n"
        for msg_id, content, is_active in messages[:10]:
            status = "🌟" if is_active else "📄"
            text += f"{status} {content[:50]}...\n"
        await event.edit(text, buttons=messages_buttons())
    elif data == "add_message":
        await event.edit("📝 Send the message text:")
        TEMP[ADMIN_ID] = "new_message"
    elif data == "set_active_message":
        messages = db.get_all_messages()
        if not messages:
            await event.answer("No messages!", alert=True)
            return
        btns = []
        for msg_id, content, is_active in messages[:10]:
            status = "🌟" if is_active else "📄"
            btns.append([Button.inline(f"{status} {content[:25]}", f"set_active_{msg_id}".encode())])
        btns.append([Button.inline("⬅️ Back", b"manage_messages")])
        await event.edit("Select active message:", buttons=btns)
    elif data.startswith("set_active_"):
        msg_id = data.replace("set_active_", "")
        db.set_active_message(msg_id)
        await event.answer("✅ Active message set!", alert=True)
        await event.edit("📝 Messages", buttons=messages_buttons())
    elif data == "delete_message":
        messages = db.get_all_messages()
        if not messages:
            await event.answer("No messages!", alert=True)
            return
        btns = []
        for msg_id, content, is_active in messages[:10]:
            btns.append([Button.inline(f"🗑 {content[:25]}", f"del_msg_{msg_id}".encode())])
        btns.append([Button.inline("⬅️ Back", b"manage_messages")])
        await event.edit("Select message to delete:", buttons=btns)
    elif data.startswith("del_msg_"):
        msg_id = data.replace("del_msg_", "")
        db.delete_message(msg_id)
        await event.answer("✅ Message deleted!", alert=True)
        await event.edit("📝 Messages", buttons=messages_buttons())
    elif data == "view_chats":
        groups = db.get_all_groups()
        text = f"📢 **Groups** ({len(groups)})\n\n"
        for gid, name, members, posts, bl, last in groups[:15]:
            text += f"• {name[:25]} | 👥 {members or '?'}\n"
        await event.edit(text, buttons=main_buttons())
    elif data == "view_joined_links":
        links = db.get_joined_links(20)
        if not links:
            await event.edit("No links", buttons=main_buttons())
            return
        text = "🔗 **Links**\n\n"
        for link, group_name, joined_at, joined_by in links[:15]:
            text += f"• {group_name[:30]}\n"
        await event.edit(text, buttons=main_buttons())
    elif data == "contacts_menu":
        await event.edit("📞 **Contacts**", buttons=contacts_buttons())
    elif data == "add_contact":
        await event.edit("📱 Send: Name + Phone\nExample: Ahmed +967712345678")
        TEMP[ADMIN_ID] = "add_contact"
    elif data == "list_contacts":
        contacts = db.get_contacts()
        if not contacts:
            await event.edit("No contacts", buttons=contacts_buttons())
            return
        text = "📞 **Contacts**\n\n"
        for cid, name, phone, _, _ in contacts[:15]:
            text += f"• {name}: {phone}\n"
        await event.edit(text, buttons=contacts_buttons())
    elif data == "start_p":
        if not USER_CLIENTS:
            return await event.answer("❌ No accounts!", alert=True)
        if is_posting:
            return await event.answer("⚠️ Already posting!", alert=True)
        is_posting = True
        asyncio.create_task(poster())
        await event.edit("🚀 Posting started!", buttons=main_buttons())
    elif data == "stop_p":
        is_posting = False
        await event.edit("🛑 Posting stopped!", buttons=main_buttons())

# ==================== النشر ====================

async def poster():
    global is_posting
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
            
            group = random.choice(groups)
            group_id, group_name = group[0], group[1]
            
            try:
                entity = await client.get_entity(int(group_id))
                await client.send_message(entity, active_msg['content'])
                db.log_post(phone, group_id, group_name, 'success')
                logger.success(f"✅ Posted in {group_name[:30]}")
            except Exception as e:
                logger.error(f"❌ Failed: {str(e)[:50]}")
            
            await asyncio.sleep(SETTINGS.get('interval', 5))
        except Exception as e:
            await asyncio.sleep(10)

# ==================== الدالة الرئيسية ====================

async def main():
    global bot, start_time
    start_time = datetime.now()
    
    print("=" * 50)
    print("🤖 Bot Starting - No Lock Version")
    print("=" * 50)
    
    # Flask
    web_thread = Thread(target=run_web, daemon=True)
    web_thread.start()
    await asyncio.sleep(1.5)
    
    # Bot
    bot = TelegramClient('bot_session', API_ID, API_HASH)
    bot.add_event_handler(start_handler, events.NewMessage(pattern='/start'))
    bot.add_event_handler(callback_handler, events.CallbackQuery())
    
    await bot.start(bot_token=BOT_TOKEN)
    bot_username = f"@{bot.me.username}" if bot.me else "Unknown"
    print(f"✅ Bot: {bot_username}")
    
    # Load accounts
    for phone, status, _, _, _ in db.get_accounts():
        if status == 'active':
            session_str = db.get_account_session(phone)
            if session_str:
                try:
                    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
                    await client.start()
                    USER_CLIENTS[phone] = client
                except:
                    pass
    
    print(f"✅ Ready! Port: {PORT}")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
