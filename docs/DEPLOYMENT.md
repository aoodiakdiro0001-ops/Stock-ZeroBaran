<div dir="rtl">

# 🚀 Stock-ZeroBaran — دليل النشر والتفعيل

**المؤلف:** Baran Avisat | **البريد:** Baranavisat@gmail.com | **الواتساب:** 00905313263722

---

## 📋 جدول النشر الكامل

| الخطوة | المدة التقديرية | المكلّف |
|---|---|---|
| 1. إنشاء Supabase | 5 دقائق | مجاني |
| 2. إنشاء مفاتيح Gemini | 3 دقائق | مجاني |
| 3. (اختياري) إنشاء Groq | 3 دقائق | مجاني |
| 4. إنشاء بوت تليجرام | 5 دقائق | مجاني |
| 5. رفع المشروع لـ GitHub | 5 دقائق | مجاني |
| 6. إعداد Secrets في GitHub | 5 دقائق | مجاني |
| 7. تشغيل محلي للتجربة | 3 دقائق | مجاني |
| 8. تفعيل الجدولة التلقائية | 2 دقيقة | مجاني |

**الإجمالي:** ~30 دقيقة | **التكلفة:** $0

---

## 1️⃣ إنشاء قاعدة بيانات Supabase

1. اذهب إلى [supabase.com](https://supabase.com) وأنشئ حساباً مجانياً.
2. اضغط **New Project** واملأ:
   - الاسم: `stock-zerobaran`
   - كلمة مرور قوية لقاعدة البيانات
   - المنطقة: أقرب منطقة لك (مثلاً Frankfurt)
3. انتظر ~2 دقيقة لإنشاء المشروع.
4. اذهب إلى **SQL Editor** (في القائمة الجانبية).
5. انسخ كامل محتوى `src/database/schema.sql` من هذا المشروع والصقه.
6. اضغط **Run** — سيتم إنشاء كل الجداول والفهارس والسياسات.
7. اذهب إلى **Project Settings → API** وانسخ:
   - `Project URL` (مثل: `https://abcxyz.supabase.co`)
   - `service_role` secret key (احتفظ بها سرّاً!)

> 💡 **حدود الطبقة المجانية:** 500MB تخزين، 50,000 صف بالشهر — كافية لمتجر صغير-متوسط.

---

## 2️⃣ الحصول على مفتاح Google Gemini API (مجاني)

1. اذهب إلى [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
2. سجّل الدخول بحساب Google.
3. اضغط **Create API Key**.
4. اختر مشروعاً (أو أنشئ واحداً).
5. انسخ المفتاح (يبدأ بـ `AIza...`).

> 💡 **حدود الطبقة المجانية لـ Gemini 1.5 Flash:**
> - 15 طلب/دقيقة
> - 1,500 طلب/يوم
> - مجاني 100%

---

## 3️⃣ (اختياري) الحصول على مفتاح Groq API

بديل مجاني سريع جداً (Llama 3.3 70B Versatile):

1. اذهب إلى [console.groq.com](https://console.groq.com).
2. أنشئ حساباً مجاناً.
3. **API Keys → Create API Key**.
4. انسخ المفتاح (يبدأ بـ `gsk_...`).

> 💡 **حدود الطبقة المجانية:** 30 طلب/دقيقة، ~14,400 طلب/يوم.

---

## 4️⃣ إنشاء بوت تليجرام

1. افتح تليجرام وتحدّث إلى [@BotFather](https://t.me/BotFather).
2. أرسل `/newbot`.
3. اتبع التعليمات:
   - اختر اسماً للبوت: `Stock-ZeroBaran Alerts`
   - اختر username: `my_stock_alerts_bot` (يجب أن ينتهي بـ `_bot`)
4. سيُعطيك توكن (مثل: `7891234567:AAEx...`).
5. اضغط على الرابط لفتح البوت وأرسل `/start`.
6. للحصول على `chat_id`:
   - تحدّث إلى [@userinfobot](https://t.me/userinfobot)
   - سيُرسل لك معرّفك الرقمي (مثل: `123456789`)

**للتنبيهات لمجموعة (قنوات الفريق):**
- أضف البوت إلى المجموعة
- استخرج `chat_id` من رسالة @userinfobot في المجموعة

---

## 5️⃣ رفع المشروع إلى GitHub

```bash
# في مجلد المشروع
git init
git add .
git commit -m "Stock-ZeroBaran v1.0.0 — Initial release"
git branch -M main
git remote add origin https://github.com/USERNAME/Stock-ZeroBaran.git
git push -u origin main
```

> 💡 **تأكّد أن ملف `.env` غير مرفوع** (موجود في `.gitignore`).

---

## 6️⃣ إضافة Secrets في GitHub

1. في صفحة المستودع: **Settings → Secrets and variables → Actions**.
2. اضغط **New repository secret** لكل مفتاح:

| الاسم | القيمة |
|---|---|
| `SUPABASE_URL` | `https://abcxyz.supabase.co` |
| `SUPABASE_KEY` | مفتاح `service_role` من Supabase |
| `GEMINI_API_KEY` | مفتاح Gemini |
| `GROQ_API_KEY` | مفتاح Groq (اختياري) |
| `TELEGRAM_BOT_TOKEN` | توكن البوت |
| `TELEGRAM_CHAT_ID` | معرّف الدردشة |

3. (اختياري) في **Variables** (وليس Secrets):
   - `AI_ENGINE` = `gemini` أو `groq`
   - `TIMEZONE` = `Asia/Baghdad` (أو منطقتك)

---

## 7️⃣ التشغيل المحلي للتجربة

```bash
# تثبيت التبعيات
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# إعداد البيئة
cp .env.example .env
# عدّل .env بالمفاتيح الحقيقية

# تعبئة بيانات تجريبية
python scripts/seed_sample_data.py

# فحص تليجرام (اختياري)
python scripts/setup_telegram.py

# تشغيل دورة كاملة
python scripts/run_inventory_check.py

# تشغيل لوحة التحكم
streamlit run src/dashboard/app.py
```

---

## 8️⃣ تفعيل الجدولة التلقائية

### عبر GitHub Actions (مجاني ومضمّن)

ملف `inventory-cron.yml` يُشغّل النظام يومياً الساعة 08:00 UTC.

**لتفعيله:**
1. اذهب إلى تبويب **Actions** في المستودع.
2. اضغط على **Stock-ZeroBaran Daily Inventory Check**.
3. اضغط **Enable workflow**.
4. لتشغيل فوري: اضغط **Run workflow**.

### لتعديل وقت التشغيل

في `.github/workflows/inventory-cron.yml`:
```yaml
schedule:
  - cron: '0 8 * * *'   # كل يوم 08:00 UTC
  - cron: '0 */6 * * *' # كل 6 ساعات (أكثر تكراراً)
```

> ⚠️ **ملاحظة:** GitHub قد يؤخر المجدول 5-30 دقيقة أحياناً. هذا طبيعي للطبقة المجانية.

---

## 🔄 البدائل المحلية (بلا إنترنت خارجي)

إن أردت تشغيل النظام بالكامل **دون اتصال بأي خدمة خارجية**:

### 1. قاعدة بيانات محلية SQLite بدلاً من Supabase
```bash
# أضف لـ requirements.txt
sqlalchemy==2.0.30
# واستبدل supabase_client.py بعميل SQLAlchemy
```

### 2. جدولة محلية عبر cron (Linux/Mac) أو Task Scheduler (Windows)
```bash
# Linux/Mac — كل يوم 8 صباحاً
crontab -e
# أضف:
0 8 * * * /path/to/venv/bin/python /path/to/scripts/run_inventory_check.py
```

```powershell
# Windows — Task Scheduler
schtasks /create /tn "StockZeroBaranDaily" /tr "python C:\Stock-ZeroBaran\scripts\run_inventory_check.py" /sc daily /st 08:00
```

### 3. تنبيهات بريد إلكتروني بدلاً من تليجرام
يمكنك إضافة `send_email()` في `alerts.py` باستخدام SMTP مجاني (Gmail مع App Password).

---

## 📈 مراقبة الأداء

### فحص سجلات التنفيذ
- محلياً: `logs/stockzerobaran.log`
- على GitHub: تبويب **Actions** → اضغط على آخر تشغيل → اعرض الـ logs

### متابعة استهلاك حصص API
- Gemini: [aistudio.google.com](https://aistudio.google.com) → Usage
- Groq: [console.groq.com/usage](https://console.groq.com/usage)
- Supabase: Dashboard → Reports → API usage

### تنبيهات استهلاك عالٍ
في ملف `.env`، يمكنك تقليل تكرار الفحص إذا تجاوزت الحصص:
```bash
# بدل جدولة يومية، اجعلها كل 3 أيام
# في inventory-cron.yml: cron: '0 8 */3 * *'
```

---

## 🆘 حل المشاكل الشائعة

| المشكلة | الحل |
|---|---|
| `Supabase credentials غير مُهيّأة` | تأكّد من تعبئة `.env` |
| `GEMINI_API_KEY غير مُهيّأ` | أضف المفتاح في `.env` |
| `فشل تليجرام 401` | توكن البوت خاطئ |
| `فشل تليجرام 400` | `chat_id` خاطئ |
| `NaN` في التنبؤات | محرك AI لم يُرجع JSON — يُستخدم fallback تلقائياً |
| `GitHub Actions didn't run` | المجدول قد يتأخر؛ شغّل يدوياً عبر **Run workflow** |
| لا تظهر بيانات في اللوحة | شغّل `seed_sample_data.py` أولاً |

---

## 📞 الدعم

**للدعم الفني والاستفسارات التجارية:**

| القناة | المعرّف |
|---|---|
| 📧 البريد | `Baranavisat@gmail.com` |
| 💬 واتساب | `00905313263722` |

---

© 2026 Baran Avisat — جميع الحقوق محفوظة

</div>
