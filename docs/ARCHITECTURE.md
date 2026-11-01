<div dir="rtl">

# 📐 Stock-ZeroBaran — تفصيل البنية الهندسية

**المؤلف:** Baran Avisat | **البريد:** Baranavisat@gmail.com | **الواتساب:** 00905313263722

---

## 1. نمط البنية المعمارية

يعتمد النظام على **البنية الطبقية (Layered Architecture)** مع فصل واضح للمسؤوليات:

```
┌───────────────────────────────────────────────────────────────┐
│  طبقة العرض (Presentation Layer)                              │
│  ├─ Streamlit Dashboard (src/dashboard/app.py)               │
│  └─ Telegram Bot (alerts.py)                                 │
└────────────────────────┬──────────────────────────────────────┘
                         ▼
┌───────────────────────────────────────────────────────────────┐
│  طبقة الأعمال (Business Logic Layer)                          │
│  ├─ InventoryEngine (inventory.py) — المراقبة والحسابات       │
│  ├─ ForecastingEngine (forecasting.py) — التنبؤ              │
│  └─ AlertEngine (alerts.py) — صياغة وإرسال التنبيهات         │
└────────────────────────┬──────────────────────────────────────┘
                         ▼
┌───────────────────────────────────────────────────────────────┐
│  طبقة الوصول للبيانات (Data Access Layer)                    │
│  └─ SupabaseClient (supabase_client.py)                      │
│     • retry مع exponential backoff                           │
│     • upsert / select / insert / update                      │
└────────────────────────┬──────────────────────────────────────┘
                         ▼
┌───────────────────────────────────────────────────────────────┐
│  طبقة التخزين (Storage Layer)                                │
│  ├─ Supabase PostgreSQL (الأساسي)                            │
│  └─ CSV محلي (احتياطي عند غياب Supabase)                     │
└───────────────────────────────────────────────────────────────┘
```

---

## 2. مبدأ فصل المسؤوليات (Single Responsibility)

| المكوّن | المسؤولية الوحيدة |
|---|---|
| `inventory.py` | حساب الكميات والمعدلات فقط |
| `forecasting.py` | التنبؤ والاستدلال فقط |
| `alerts.py` | الصياغة والإرسال فقط |
| `supabase_client.py` | CRUD في قاعدة البيانات فقط |
| `helpers.py` | الدوال المشتركة (تنسيق، تواريخ، سجل) |
| `settings.py` | قراءة الإعدادات من البيئة |
| `run_inventory_check.py` | تنسيق سير العمل فقط |

---

## 3. مخطط تدفق البيانات (Data Flow)

```
   ┌──────────────────────┐
   │  المبيعات اليومية     │ ← CSV / Supabase sales table
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │  InventoryEngine     │
   │  • load_movements()  │
   │  • compute_current_  │
   │    stock()           │
   │  • compute_daily_    │
   │    consumption()     │
   │  • compute_days_     │
   │    until_stockout()  │
   └──────────┬───────────┘
              │ List[StockSnapshot]
              ▼
   ┌──────────────────────┐
   │  ForecastingEngine   │
   │  • forecast_product()│ ← Gemini / Groq API
   │  • forecast_all()    │
   │  • detect_seasonality│
   └──────────┬───────────┘
              │ List[DemandForecast]
              ▼
   ┌──────────────────────┐
   │  AlertEngine         │
   │  • dispatch_critical │ → Telegram
   │  • dispatch_low      │
   │  • dispatch_slow     │
   │  • dispatch_daily    │
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │  Supabase            │
   │  • stock_status      │ (upsert)
   │  • forecasts         │ (insert)
   │  • alerts_log        │ (insert)
   └──────────────────────┘
```

---

## 4. تصميم قابل للتوسعة (Extensibility)

### محرك AI قابل للتبديل
```python
AI_ENGINE=gemini  # أو groq
```
النظام يبني `ForecastingEngine(engine=...)` ويستدعي المحرك المختار،
ثم يتبدّل تلقائياً إلى الآخر عند الفشل (fault tolerance).

### محرك قاعدة بيانات قابل للتبديل
- `SupabaseClient.available` يكتشف توفّر الاتصال
- عند غيابه، يُحمّل البيانات من CSV تلقائياً (Local mode)
- يمكن إضافة محركات أخرى (Firebase, SQLite) بتوسعة `SupabaseClient`

### قنوات تنبيه قابلة للإضافة
`AlertEngine.send()` حالياً يرسل لتليجرام، لكن يمكن توسعته بسهولة:
- إضافة `send_email()` عبر SMTP مجاني
- إضافة `send_slack()` عبر Incoming Webhook
- إضافة `send_whatsapp()` عبر WhatsApp Cloud API

---

## 5. خصائص الموثوقية (Reliability)

### إعادة المحاولة (Retry)
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(DatabaseError),
)
```
كل عملية قاعدة بيانات تُعاد 3 مرات مع backoff أُسّي.

### التسجيل الشامل (Logging)
- `colorlog` للألوان في الطرفية
- ملف سجل دائم في `logs/stockzerobaran.log`
- مستويات: DEBUG / INFO / WARNING / ERROR / CRITICAL

### معالجة الاستثناءات
- كل طبقة تلتقط أخطاءها ولا تنهار النظام بالكامل
- التنبؤ الإحصائي (fallback) عند غياب AI
- وضع CSV المحلي عند غياب Supabase

---

## 6. نموذج البيانات (Data Model)

### المنتج (Product)
```
Product {
  id: UUID (PK)
  sku: Text (Unique)
  name: Text
  category: Text
  unit_cost: Decimal(12,2)
  selling_price: Decimal(12,2)
  reorder_point: Integer        # الحد الأدنى للطلب
  reorder_qty: Integer          # الكمية المثالية للطلب
  safety_stock: Integer         # مخزون الأمان
  supplier_id: UUID (FK)
}
```

### الحركة (Movement)
```
Movement {
  id: UUID (PK)
  product_id: UUID (FK)
  movement_type: Enum(in, out, adjustment_in, adjustment_out)
  quantity: Decimal(12,2)
  movement_date: Timestamptz
  reference: Text               # رقم الفاتورة
}
```

### لقطة الحالة (StockSnapshot)
```
StockSnapshot {
  product_id: UUID
  current_stock: Decimal
  daily_consumption_rate: Decimal
  days_until_stockout: Decimal?
  stock_health: Enum(healthy, low, critical, out, overstock)
  last_movement_date: Timestamptz
}
```

### التنبؤ (Forecast)
```
DemandForecast {
  product_id: UUID
  forecast_date: Date
  expected_demand: Decimal
  confidence: Decimal(5,2)      # 0-100
  suggested_reorder: Decimal
  model_used: Enum(gemini, groq, fallback)
  reasoning: Text
  seasonal_note: Text
}
```

---

## 7. اعتبارات الأداء

| العملية | التعقيد | الذاكرة |
|---|---|---|
| حساب المخزون الحالي | O(N) لكل المنتجات | DataFrame في الذاكرة |
| حساب معدل الاستهلاك | O(N×W) حيث W = النافذة | متجه Pandas |
| التنبؤ لمنتج واحد | استدعاء API واحد (~1-3 ثانية) | برومبت واحد |
| التنبؤ لكل المنتجات | O(N) استدعاءات API | يتطلّب batch للأنظمة الكبيرة |

**للأنظمة الكبيرة (>100 منتج):**
- استخدم Gemini Batch API (مجاني للنسخ الدفعية)
- أو فهرسة جدول `inventory_movements` على `product_id + movement_date`

---

## 8. ملاحظات أمنية

- ✅ كل المفاتيح في `.env` (محذوف من Git)
- ✅ Row Level Security مُفعّل في Supabase
- ✅ استخدام Service Role Key فقط للعمليات الداخلية
- ✅ لا تُرسل بيانات شخصية للعملاء لأي طرف خارجي
- ⚠️ في الإنتاج، استخدم مفتاح Service Role بدلاً من Anon Key

---

</div>
