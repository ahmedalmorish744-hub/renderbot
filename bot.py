#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════╗
║     🤖 بوت النشر الخارق - نسخة MongoDB الخارجية              ║
║     حفظ دائم للبيانات + حماية كاملة + تشفير ذكي              ║
╚═══════════════════════════════════════════════════════════════╝
"""

import asyncio
import re
import os
import random
import json
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
from pymongo import MongoClient

# ==================== الإعدادات الأساسية ====================

API_ID = int(os.environ.get('API_ID', 33957094))
API_HASH = os.environ.get('API_HASH', "35e04f65846f09700aac0696a59f1a37")
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8713124620:AAFQGCd4IhcKql1g1mKJXnF_ePHGh0npwLo")
ADMIN_ID = int(os.environ.get('ADMIN_ID', 7853478744))
MONGO_URI = os.environ.get('MONGO_URI', "")

# ==================== إعدادات التشغيل ====================

LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# ==================== خادم الويب ====================
app = Flask(__name__)

@app.route('/')
def home(): 
    return jsonify({'status': 'online', 'msg': '🤖 البوت يعمل بنجاح مع MongoDB!', 'time': str(datetime.now())})

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

# ==================== قاعدة البيانات (MongoDB) ====================

class Database:
    def __init__(self, uri):
        if not uri:
            logger.critical("❌ لم يتم العثور على MONGO_URI في المتغيرات البيئية!")
            sys.exit(1)
        try:
            self.client = MongoClient(uri)
            self.db = self.client['telegram_bot']
            # المجموعات
            self.settings = self.db['settings']
            self.messages = self.db['messages']
            self.accounts = self.db['accounts']
            self.groups = self.db['groups']
            self.history = self.db['history']
            self.links = self.db['links']
            logger.success("✅ متصل بقاعدة بيانات MongoDB بنجاح")
            
            # تهيئة الرسالة الافتراضية إذا كانت فارغة
            if self.messages.count_documents({}) == 0:
                self.save_message("default", "📢 مرحباً بك في بوت النشر!", is_active=True)
        except Exception as e:
            logger.critical(f"💥 فشل الاتصال بـ MongoDB: {e}")
            sys.exit(1)

    # الإعدادات
    def save_setting(self, key, value):
        self.settings.update_one({'key': key}, {'$set': {'value': value, 'updated_at': datetime.now()}}, upsert=True)

    def get_setting(self, key, default=None):
        doc = self.settings.find_one({'key': key})
        return doc['value'] if doc else default

    def get_all_settings(self):
        docs = self.settings.find({})
        return {doc['key']: doc['value'] for doc in docs}

    # الرسائل
    def save_message(self, msg_id, content, is_active=False):
        if is_active:
            self.messages.update_many({}, {'$set': {'is_active': False}})
        self.messages.update_one(
            {'msg_id': msg_id},
            {'$set': {'content': content, 'created_at': datetime.now(), 'is_active': is_active}},
            upsert=True
        )

    def get_all_messages(self):
        docs = self.messages.find({}).sort('created_at', -1)
        return [(d['msg_id'], d['content'], d['is_active']) for d in docs]

    def get_active_message(self):
        doc = self.messages.find_one({'is_active': True})
        if doc:
            return {'id': doc['msg_id'], 'content': doc['content']}
        return None

    def set_active_message(self, msg_id):
        self.messages.update_many({}, {'$set': {'is_active': False}})
        self.messages.update_one({'msg_id': msg_id}, {'$set': {'is_active': True}})

    def delete_message(self, msg_id):
        self.messages.delete_one({'msg_id': msg_id})

    # الحسابات
    def add_account(self, phone, session_str):
        self.accounts.update_one(
            {'phone': phone},
            {'$set': {
                'session_str': session_str,
                'added_at': datetime.now(),
                'last_active': datetime.now(),
                'status': 'active',
                'total_posts': 0,
                'success_posts': 0,
                'failed_posts': 0
            }},
            upsert=True
        )

    def remove_account(self, phone):
        self.accounts.delete_one({'phone': phone})

    def get_accounts(self):
        docs = self.accounts.find({}).sort('added_at', -1)
        return [(d['phone'], d['status'], d.get('total_posts', 0), d.get('success_posts', 0), d.get('failed_posts', 0)) for d in docs]

    def update_account_status(self, phone, status):
        self.accounts.update_one({'phone': phone}, {'$set': {'status': status, 'last_active': datetime.now()}})

    def increment_account_posts(self, phone, success=True):
        field = 'success_posts' if success else 'failed_posts'
        self.accounts.update_one({'phone': phone}, {'$inc': {'total_posts': 1, field: 1}})

    # المجموعات
    def add_group(self, group_id, name, username, gtype, members, phone):
        self.groups.update_one(
            {'group_id': str(group_id)},
            {'$set': {
                'group_name': name,
                'group_username': username,
                'group_type': gtype,
                'members_count': members,
                'added_by': phone,
                'added_at': datetime.now(),
                'last_post': datetime.now()
            }, '$inc': {'post_count': 1}},
            upsert=True
        )

    def get_all_groups(self):
        docs = self.groups.find({})
        return [(d['group_id'], d['group_name'], d.get('members_count', 0), d.get('post_count', 0), d.get('is_blacklisted', False), d.get('last_post')) for d in docs]

    def search_groups(self, query):
        docs = self.groups.find({
            '$or': [
                {'group_name': {'$regex': query, '$options': 'i'}},
                {'group_id': query}
            ]
        }).limit(10)
        return [(d['group_id'], d['group_name'], d.get('members_count', 0)) for d in docs]

    def blacklist_group(self, group_id):
        self.groups.update_one({'group_id': str(group_id)}, {'$set': {'is_blacklisted': True}}, upsert=True)

    def whitelist_group(self, group_id):
        self.groups.update_one({'group_id': str(group_id)}, {'$set': {'is_blacklisted': False}})

    def get_blacklisted_groups(self):
        docs = self.groups.find({'is_blacklisted': True})
        return [(d['group_id'], d['group_name']) for d in docs]

    # السجل
    def log_post(self, phone, group_id, group_name, status, error=None):
        self.history.insert_one({
            'phone': phone,
            'group_id': str(group_id),
            'group_name': group_name,
            'sent_at': datetime.now(),
            'status': status,
            'error': error
        })
        self.increment_account_posts(phone, success=(status == 'success'))

    def get_posting_stats(self):
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        total = self.history.count_documents({'sent_at': {'$gte': today}})
        success = self.history.count_documents({'sent_at': {'$gte': today}, 'status': 'success'})
        failed = total - success
        return {'total': total, 'success': success, 'failed': failed}

    def get_recent_posts(self, limit=10):
        docs = self.history.find({}).sort('sent_at', -1).limit(limit)
        return [(d['phone'], d['group_name'], d['status'], d['sent_at'].isoformat()) for d in docs]

    # الروابط
    def add_joined_link(self, link, group_id, group_name, phone):
        self.links.insert_one({
            'link': link,
            'group_id': str(group_id),
            'group_name': group_name,
            'joined_at': datetime.now(),
            'joined_by': phone
        })

    def get_joined_links(self, limit=20):
        docs = self.links.find({}).sort('joined_at', -1).limit(limit)
        return [(d['link'], d['group_name'], d['joined_at'].isoformat(), d['joined_by']) for d in docs]

    def get_joined_links_count(self):
        return self.links.count_documents({})

db = Database(MONGO_URI)

# ==================== نظام التشفير الاحترافي ====================

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
        self.last_posts = {}
        self.warmed_groups = set()
        self.synonyms = {'اشترك': ['انضم', 'تابع', 'كن معنا'], 'قناة': ['مجموعة', 'منصة', 'صفحتنا'], 'دعم': ['مساندة', 'متابعة']}
        self.templates = ["{}", "✨ {} ✨", "🔹 {}\n🔸 تابعنا للمزيد", "📢 {}\n\n💡 لا تفوت الفرصة"]
    
    def disguise_text(self, text):
        result = text
        for keyword, replacements in self.synonyms.items():
            if keyword in result and random.random() > 0.7:
                result = result.replace(keyword, random.choice(replacements))
        return result
    
    def disguise_link(self, text):
        return re.sub(r't\.me', 't\u200B.me', text)
    
    def random_delay(self, base_delay=8):
        return random.randint(int(base_delay * 0.8), int(base_delay * 1.5))
    
    def get_variation(self, text, variation_count=6):
        variations = set()
        for _ in range(variation_count * 2):
            variant = text
            if random.random() > 0.6: variant = self.disguise_text(variant)
            if random.random() > 0.7: variant = self.disguise_link(variant)
            if random.random() > 0.8: variant = random.choice(self.templates).format(variant)
            variations.add(variant)
        return list(variations)[:variation_count]
    
    async def send_safe(self, client, chat_id, original_text, group_name=""):
        try:
            variations = self.get_variation(original_text, 6)
            final_text = random.choice(variations)
            final_text = advanced_encryption.encrypt_smart(final_text)
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
        gid = str(group_id)
        self.failed_attempts[gid] = self.failed_attempts.get(gid, 0) + 1
        if self.failed_attempts[gid] >= 3:
            self.banned_groups.add(gid)
            logger.warning(f"🚫 تم حظر المجموعة {gid} مؤقتاً")
    
    def is_banned(self, group_id):
        return str(group_id) in self.banned_groups
    
    def clear_banned(self, group_id):
        gid = str(group_id)
        self.banned_groups.discard(gid)
        self.failed_attempts.pop(gid, None)
    
    def get_banned_count(self):
        return len(self.banned_groups)

group_blacklist = GroupBlacklistManager()

# ==================== المتغيرات العامة ====================

USER_CLIENTS = {}
SETTINGS = {
    'interval': 10,
    'encryption': True,
    'auto_join_enabled': True,
    'save_joined_links': True,
    'anti_detection': True,
    'warm_up_enabled': False
}
SETTINGS.update(db.get_all_settings())
TEMP = {}
is_posting = False
bot_client = None
start_time = datetime.now()

# ==================== وظائف مساعدة ====================

def format_number(num):
    if num >= 1000000: return f"{num/1000000:.1f}M"
    if num >= 1000: return f"{num/1000:.1f}K"
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
        [Button.inline("📈 إحصائيات", b"stats"), Button.inline("🔗 الروابط", b"view_joined_links")]
    ]

def messages_buttons():
    return [[Button.inline("📋 عرض الكل", b"list_messages")], [Button.inline("➕ إضافة جديدة", b"add_message")], [Button.inline("✅ تعيين نشطة", b"set_active_message")], [Button.inline("🗑 حذف رسالة", b"delete_message")], [Button.inline("⬅️ عودة", b"back")]]

def advanced_buttons():
    auto_join = "✅" if SETTINGS.get('auto_join_enabled', True) else "❌"
    save_links = "✅" if SETTINGS.get('save_joined_links', True) else "❌"
    return [
        [Button.inline(f"🤖 انضمام تلقائي {auto_join}", b"toggle_autojoin")],
        [Button.inline(f"💾 حفظ الروابط {save_links}", b"toggle_save_links")],
        [Button.inline("🚫 إدارة المحظورات", b"blacklist_menu")],
        [Button.inline("⬅️ عودة", b"back")]
    ]

# ==================== المعالجات ====================

async def start_handler(event):
    if event.sender_id != ADMIN_ID: return
    accounts = db.get_accounts()
    groups = db.get_all_groups()
    active_msg = db.get_active_message()
    
    await event.respond(
        f"👋 **أهلاً بك في بوت النشر (نسخة MongoDB)!**\n\n"
        f"📊 **الإحصائيات:**\n"
        f"• الحسابات: {len(accounts)}\n"
        f"• المجموعات: {len(groups)}\n"
        f"• الرسائل: {len(db.get_all_messages())}\n\n"
        f"📨 **الرسالة النشطة:**\n{active_msg['content'][:100] if active_msg else 'لا توجد'}\n\n"
        f"استخدم الأزرار للتحكم:", 
        buttons=main_buttons()
    )

async def callback_handler(event):
    if event.sender_id != ADMIN_ID: return
    global is_posting
    data = event.data.decode()
    
    if data == "status": await show_status(event)
    elif data == "stats": await show_stats(event)
    elif data == "add":
        await event.edit("📱 أرسل رقم الهاتف مع رمز الدولة (مثال: +967...)")
        TEMP[ADMIN_ID] = "phone"
    elif data == "del_list": await show_delete_list(event)
    elif data.startswith("rm_"): await delete_account(event, data.replace("rm_", ""))
    elif data == "time":
        await event.edit("⏱ أرسل الفاصل الزمني (10-120 ثانية):")
        TEMP[ADMIN_ID] = "time"
    elif data == "toggle_enc":
        SETTINGS['encryption'] = not SETTINGS['encryption']
        db.save_setting('encryption', SETTINGS['encryption'])
        await event.edit("👋 لوحة التحكم:", buttons=main_buttons())
    elif data == "toggle_anti":
        SETTINGS['anti_detection'] = not SETTINGS.get('anti_detection', True)
        db.save_setting('anti_detection', SETTINGS['anti_detection'])
        await event.edit("👋 لوحة التحكم:", buttons=main_buttons())
    elif data == "view_chats": await show_groups(event)
    elif data == "advanced": await event.edit("⚙️ الإعدادات المتقدمة", buttons=advanced_buttons())
    elif data == "back": await event.edit("👋 لوحة التحكم الرئيسية", buttons=main_buttons())
    elif data == "manage_messages": await event.edit("📝 **إدارة الرسائل**", buttons=messages_buttons())
    elif data == "list_messages": await list_all_messages(event)
    elif data == "add_message":
        await event.edit("📝 **أرسل نص الرسالة الجديدة:**")
        TEMP[ADMIN_ID] = "new_message"
    elif data == "set_active_message": await show_set_active_message(event)
    elif data.startswith("set_active_"):
        db.set_active_message(data.replace("set_active_", ""))
        await event.edit("📝 إدارة الرسائل", buttons=messages_buttons())
    elif data == "delete_message": await show_delete_message(event)
    elif data.startswith("del_msg_"):
        db.delete_message(data.replace("del_msg_", ""))
        await event.edit("📝 إدارة الرسائل", buttons=messages_buttons())
    elif data == "start_p":
        if not is_posting:
            is_posting = True
            asyncio.create_task(poster())
            await event.answer("🚀 بدأ النشر!", alert=True)
        else: await event.answer("⚠️ النشر يعمل بالفعل", alert=True)
    elif data == "stop_p":
        is_posting = False
        await event.answer("🛑 تم إيقاف النشر", alert=True)
    elif data == "view_joined_links": await show_joined_links(event)

# دالة النشر
async def poster():
    global is_posting
    logger.info("🚀 بدء النشر...")
    while is_posting:
        try:
            if not USER_CLIENTS:
                await asyncio.sleep(10); continue
            active_msg = db.get_active_message()
            if not active_msg:
                await asyncio.sleep(10); continue
            
            for phone, client in list(USER_CLIENTS.items()):
                if not is_posting: break
                try:
                    async for dialog in client.iter_dialogs():
                        if not is_posting: break
                        if not dialog.is_group: continue
                        
                        # فحص القائمة السوداء
                        blacklisted = [g[0] for g in db.get_blacklisted_groups()]
                        if str(dialog.id) in blacklisted or group_blacklist.is_banned(dialog.id): continue
                        
                        success, result = await anti_detection.send_safe(client, dialog.id, active_msg['content'], dialog.name)
                        if success:
                            db.log_post(phone, dialog.id, dialog.name, 'success')
                            logger.info(f"✅ [{phone[-8:]}] أرسل لـ {dialog.name[:30]}")
                        else:
                            db.log_post(phone, dialog.id, dialog.name, 'failed', result)
                            group_blacklist.record_failure(dialog.id, result)
                        
                        await asyncio.sleep(anti_detection.random_delay(SETTINGS.get('interval', 10)))
                except Exception as e:
                    logger.error(f"❌ خطأ في الحساب {phone}: {e}")
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"💥 خطأ في حلقة النشر: {e}")
            await asyncio.sleep(30)

# استعادة الجلسات
async def restore_sessions():
    accounts = db.get_accounts()
    restored = 0
    for acc in accounts:
        phone = acc[0]
        doc = db.accounts.find_one({'phone': phone})
        if doc and doc.get('session_str'):
            try:
                client = TelegramClient(StringSession(doc['session_str']), API_ID, API_HASH)
                await client.connect()
                if await client.is_user_authorized():
                    USER_CLIENTS[phone] = client
                    restored += 1
                    logger.success(f"✅ تم استعادة {phone}")
            except Exception as e:
                logger.error(f"❌ فشل استعادة {phone}: {e}")
    return restored

# وظائف العرض (Status, Stats, etc.) - مختصرة للضرورة
async def show_status(event):
    stats = db.get_posting_stats()
    text = f"📊 **حالة البوت (MongoDB)**\n\n👤 الحسابات: {len(USER_CLIENTS)}\n📨 منشورات اليوم: {stats['total']}\n✅ ناجح: {stats['success']}\n❌ فاشل: {stats['failed']}\n🔄 النشر: {'🟢 نشط' if is_posting else '🔴 متوقف'}"
    await event.edit(text, buttons=main_buttons())

async def show_stats(event):
    stats = db.get_posting_stats()
    text = f"📈 **إحصائيات**\n\nإجمالي اليوم: {stats['total']}\nنجاح: {stats['success']}\nفشل: {stats['failed']}"
    await event.edit(text, buttons=main_buttons())

async def show_delete_list(event):
    accounts = db.get_accounts()
    btns = [[Button.inline(f"🗑 {a[0]}", f"rm_{a[0]}".encode())] for a in accounts[:10]]
    btns.append([Button.inline("⬅️ عودة", b"back")])
    await event.edit("🗑 اختر حساباً للحذف", buttons=btns)

async def delete_account(event, phone):
    if phone in USER_CLIENTS:
        await USER_CLIENTS[phone].disconnect()
        del USER_CLIENTS[phone]
    db.remove_account(phone)
    await event.answer(f"✅ تم حذف {phone}", alert=True)
    await show_delete_list(event)

async def list_all_messages(event):
    msgs = db.get_all_messages()
    text = "📋 **قائمة الرسائل:**\n\n"
    for m in msgs: text += f"{'✅' if m[2] else '📄'} {m[1][:50]}...\n\n"
    await event.edit(text, buttons=messages_buttons())

async def show_set_active_message(event):
    msgs = db.get_all_messages()
    btns = [[Button.inline(f"{m[1][:20]}", f"set_active_{m[0]}".encode())] for m in msgs[:10]]
    btns.append([Button.inline("⬅️ عودة", b"manage_messages")])
    await event.edit("✅ اختر الرسالة النشطة", buttons=btns)

async def show_delete_message(event):
    msgs = db.get_all_messages()
    btns = [[Button.inline(f"🗑 {m[1][:20]}", f"del_msg_{m[0]}".encode())] for m in msgs[:10]]
    btns.append([Button.inline("⬅️ عودة", b"manage_messages")])
    await event.edit("🗑 اختر رسالة لحذفها", buttons=btns)

async def show_groups(event):
    groups = db.get_all_groups()
    text = f"📢 **المجموعات المحفوظة:** {len(groups)}\n\n"
    for g in groups[:10]: text += f"• {g[1][:30]} (📨 {g[3]})\n"
    await event.edit(text, buttons=main_buttons())

async def show_joined_links(event):
    links = db.get_joined_links(10)
    text = "🔗 **آخر الروابط:**\n\n"
    for l in links: text += f"• {l[1]} ({l[3][-8:]})\n"
    await event.edit(text, buttons=main_buttons())

# معالج النصوص
async def text_handler(event):
    state = TEMP.get(ADMIN_ID)
    text = event.message.text.strip()
    if state == "phone": await handle_phone_login(event, text)
    elif state == "new_message":
        db.save_message(f"msg_{int(time.time())}", text)
        TEMP.pop(ADMIN_ID); await event.respond("✅ تم الحفظ", buttons=messages_buttons())
    elif state == "time":
        try:
            val = int(text)
            if 10 <= val <= 120:
                SETTINGS['interval'] = val; db.save_setting('interval', val)
                TEMP.pop(ADMIN_ID); await event.respond(f"✅ تم الضبط لـ {val} ثانية", buttons=main_buttons())
        except: await event.respond("❌ أرسل رقماً")
    else:
        # انضمام تلقائي
        links = re.findall(r"(https?://t\.me/(?:joinchat/|\+)[a-zA-Z0-9_-]+|https?://t\.me/[a-zA-Z0-9_]+)", text)
        if links and USER_CLIENTS:
            link = links[0]
            await event.respond(f"🐢 جاري محاولة الانضمام لـ {link}...")
            for phone, client in USER_CLIENTS.items():
                try:
                    if "joinchat" in link or "+" in link:
                        await client(ImportChatInviteRequest(link.split('/')[-1].replace('+', '')))
                    else:
                        await client(JoinChannelRequest(link))
                    db.add_joined_link(link, "unknown", "Group", phone)
                    await event.respond(f"✅ نجح الانضمام بـ {phone[-8:]}"); break
                except Exception as e: logger.error(f"فشل {phone}: {e}")

async def handle_phone_login(event, phone):
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        await client.send_code_request(phone)
        TEMP[ADMIN_ID] = {"s": "code", "p": phone, "c": client}
        await event.respond(f"📩 أرسل الكود لـ {phone}:")
    except Exception as e: await event.respond(f"❌ خطأ: {e}")

async def handle_code_verification(event, state, code):
    try:
        client, phone = state["c"], state["p"]
        await client.sign_in(phone, code)
        USER_CLIENTS[phone] = client
        db.add_account(phone, client.session.save())
        await event.respond(f"✅ تم التفعيل {phone}!"); TEMP.pop(ADMIN_ID)
    except SessionPasswordNeededError:
        TEMP[ADMIN_ID]["s"] = "pass"
        await event.respond("🔐 أرسل كلمة المرور:")
    except Exception as e: await event.respond(f"❌ فشل: {e}")

async def handle_password(event, state, password):
    try:
        await state["c"].sign_in(password=password)
        USER_CLIENTS[state["p"]] = state["c"]
        db.add_account(state["p"], state["c"].session.save())
        await event.respond(f"✅ تم التفعيل!"); TEMP.pop(ADMIN_ID)
    except Exception as e: await event.respond(f"❌ خطأ: {e}")

# التشغيل الرئيسي
async def main():
    global bot_client, start_time
    start_time = datetime.now()
    Thread(target=run_web, daemon=True).start()
    await restore_sessions()
    bot_client = TelegramClient('bot_session', API_ID, API_HASH)
    await bot_client.start(bot_token=BOT_TOKEN)
    
    @bot_client.on(events.NewMessage(pattern='/start'))
    async def start(e): await start_handler(e)
    
    @bot_client.on(events.CallbackQuery())
    async def callback(e): await callback_handler(e)
    
    @bot_client.on(events.NewMessage)
    async def text_msg(e):
        if e.sender_id != ADMIN_ID: return
        state = TEMP.get(ADMIN_ID)
        if isinstance(state, dict) and state.get("s") == "code":
            await handle_code_verification(e, state, e.message.text.strip())
        elif isinstance(state, dict) and state.get("s") == "pass":
            await handle_password(e, state, e.message.text.strip())
        else: await text_handler(e)

    logger.success("✅ البوت جاهز (نسخة MongoDB)!")
    await bot_client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
