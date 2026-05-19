# بوت النشر الخارق 🚀

هذا البوت مصمم للنشر التلقائي في مجموعات تيليجرام مع ميزات مكافحة الحظر.

## المتطلبات البيئية (Environment Variables)

يجب ضبط المتغيرات التالية في منصة Render:

- `API_ID`: معرف API الخاص بك من my.telegram.org
- `API_HASH`: الهاش الخاص بك من my.telegram.org
- `BOT_TOKEN`: توكن البوت من @BotFather
- `ADMIN_ID`: آيدي حسابك الشخصي (ليتمكن البوت من الاستجابة لك فقط)

## الاستضافة على Render

1. ارفع هذه الملفات إلى مستودع (Repository) جديد في GitHub.
2. في Render، اختر **New Web Service**.
3. اربط مستودع GitHub الخاص بك.
4. استخدم الإعدادات التالية:
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn bot:app & python3 bot.py`
5. أضف المتغيرات البيئية المذكورة أعلاه في قسم **Environment**.
