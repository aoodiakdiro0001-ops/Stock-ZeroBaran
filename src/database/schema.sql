-- ===================================================================
-- Stock-ZeroBaran — مخطط قاعدة البيانات
-- يعمل على Supabase PostgreSQL (الطبقة المجانية)
-- المؤلف: Baran Avisat  |  Baranavisat@gmail.com  |  00905313263722
-- ===================================================================

-- تفعيل الإضافات اللازمة
create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";

-- ===================================================================
-- 1) جدول الموردين (suppliers)
-- ===================================================================
create table if not exists public.suppliers (
    id              uuid primary key default uuid_generate_v4(),
    name            text not null,
    contact_email   text,
    phone           text,
    lead_time_days  integer default 7,           -- زمن التوريد بالأيام
    country         text,
    notes           text,
    is_active       boolean default true,
    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

-- ===================================================================
-- 2) جدول المنتجات (products)
-- ===================================================================
create table if not exists public.products (
    id              uuid primary key default uuid_generate_v4(),
    sku             text unique not null,         -- الرمز التعريفي للمنتج
    name            text not null,
    name_ar         text,                         -- الاسم بالعربية
    category        text,
    unit            text default 'piece',         -- قطعة / كجم / لتر ...
    unit_cost       numeric(12,2) not null default 0,
    selling_price   numeric(12,2) not null default 0,
    reorder_point   integer default 10,           -- نقطة إعادة الطلب
    reorder_qty     integer default 50,           -- كمية إعادة الطلب المثالية
    safety_stock    integer default 5,            -- مخزون الأمان
    supplier_id     uuid references public.suppliers(id),
    is_active       boolean default true,
    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

create index if not exists idx_products_sku on public.products(sku);
create index if not exists idx_products_category on public.products(category);
create index if not exists idx_products_supplier on public.products(supplier_id);

-- ===================================================================
-- 3) جدول حركات المخزون (inventory_movements)
--   — سجل كل وارد (purchase / adjustment_in) وصادر (sale / adjustment_out)
-- ===================================================================
create table if not exists public.inventory_movements (
    id              uuid primary key default uuid_generate_v4(),
    product_id      uuid not null references public.products(id) on delete cascade,
    movement_type   text not null,                -- 'in' | 'out' | 'adjustment_in' | 'adjustment_out'
    quantity        numeric(12,2) not null,       -- موجب دائماً
    unit_cost       numeric(12,2),
    reference       text,                          -- رقم الفاتورة / الطلب
    notes           text,
    movement_date   timestamptz not null default now(),
    created_at      timestamptz default now()
);

create index if not exists idx_movements_product on public.inventory_movements(product_id);
create index if not exists idx_movements_date on public.inventory_movements(movement_date);
create index if not exists idx_movements_type on public.inventory_movements(movement_type);

-- ===================================================================
-- 4) جدول المبيعات اليومية (sales) — مصدر بيانات التنبؤ
-- ===================================================================
create table if not exists public.sales (
    id              uuid primary key default uuid_generate_v4(),
    product_id      uuid not null references public.products(id) on delete cascade,
    quantity        numeric(12,2) not null,
    unit_price      numeric(12,2) not null,
    total_amount    numeric(14,2) generated always as (quantity * unit_price) stored,
    sale_date       date not null default current_date,
    channel         text default 'retail',         -- retail / online / wholesale
    customer_ref    text,
    created_at      timestamptz default now()
);

create index if not exists idx_sales_product_date on public.sales(product_id, sale_date);
create index if not exists idx_sales_date on public.sales(sale_date);

-- ===================================================================
-- 5) جدول حالة المخزون اللحظي (stock_status) — مُحدّث آلياً
-- ===================================================================
create table if not exists public.stock_status (
    id                      uuid primary key default uuid_generate_v4(),
    product_id              uuid unique not null references public.products(id) on delete cascade,
    current_stock           numeric(12,2) default 0,
    daily_consumption_rate  numeric(12,4) default 0,  -- معدل الاستهلاك اليومي
    days_until_stockout     numeric(10,2),             -- الأيام المتبقية حتى النفاد
    stock_health            text default 'unknown',    -- healthy | low | critical | out | overstock
    last_movement_date      timestamptz,
    last_updated            timestamptz default now()
);

create index if not exists idx_stockstatus_health on public.stock_status(stock_health);
create index if not exists idx_stockstatus_days on public.stock_status(days_until_stockout);

-- ===================================================================
-- 6) جدول تنبيهات النظام (alerts_log) — أرشيف الرسائل المُرسلة
-- ===================================================================
create table if not exists public.alerts_log (
    id              uuid primary key default uuid_generate_v4(),
    product_id      uuid references public.products(id) on delete cascade,
    alert_type      text not null,                  -- stockout_critical | low_stock | reorder_suggested | slow_moving | daily_report
    severity        text default 'info',            -- info | warning | critical
    message         text not null,
    suggested_qty   numeric(12,2),
    days_left       numeric(10,2),
    channel         text default 'telegram',         -- telegram | dashboard | email
    sent_at         timestamptz default now()
);

create index if not exists idx_alerts_product on public.alerts_log(product_id);
create index if not exists idx_alerts_sent on public.alerts_log(sent_at desc);

-- ===================================================================
-- 7) جدول التنبؤات (forecasts) — مخرجات العقل التنبؤي
-- ===================================================================
create table if not exists public.forecasts (
    id                  uuid primary key default uuid_generate_v4(),
    product_id          uuid not null references public.products(id) on delete cascade,
    forecast_date       date not null default current_date,
    expected_demand     numeric(12,2),              -- الطلب المتوقع
    confidence          numeric(5,2),                -- نسبة الثقة 0-100
    suggested_reorder   numeric(12,2),               -- كمية إعادة الطلب المقترحة
    model_used          text default 'gemini',       -- gemini | groq
    reasoning           text,                         -- تفسير القرار من الذكاء الاصطناعي
    created_at          timestamptz default now()
);

create index if not exists idx_forecasts_product on public.forecasts(product_id, forecast_date desc);

-- ===================================================================
-- الدوال المُلحقة (Triggers) — تحديث updated_at تلقائياً
-- ===================================================================
create or replace function public.set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_suppliers_updated on public.suppliers;
create trigger trg_suppliers_updated before update on public.suppliers
    for each row execute function public.set_updated_at();

drop trigger if exists trg_products_updated on public.products;
create trigger trg_products_updated before update on public.products
    for each row execute function public.set_updated_at();

-- ===================================================================
-- سياسات الأمان (Row Level Security) — قابلة للتعديل حسب الحاجة
-- ===================================================================
alter table public.suppliers           enable row level security;
alter table public.products            enable row level security;
alter table public.inventory_movements enable row level security;
alter table public.sales               enable row level security;
alter table public.stock_status        enable row level security;
alter table public.alerts_log          enable row level security;
alter table public.forecasts           enable row level security;

-- السماح بالوصول الكامل لخدمة النظام (Service Role Key)
-- ملاحظة: عدّل هذه السياسات في الإنتاج حسب احتياجاتك الأمنية
create policy "enable_all_for_service" on public.suppliers
    for all using (true) with check (true);
create policy "enable_all_for_service" on public.products
    for all using (true) with check (true);
create policy "enable_all_for_service" on public.inventory_movements
    for all using (true) with check (true);
create policy "enable_all_for_service" on public.sales
    for all using (true) with check (true);
create policy "enable_all_for_service" on public.stock_status
    for all using (true) with check (true);
create policy "enable_all_for_service" on public.alerts_log
    for all using (true) with check (true);
create policy "enable_all_for_service" on public.forecasts
    for all using (true) with check (true);

-- ===================================================================
-- نهاية المخطط — ابدأ بتشغيل scripts/seed_sample_data.py لتعبئة بيانات تجريبية
-- ===================================================================
