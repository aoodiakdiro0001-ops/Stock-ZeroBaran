#!/usr/bin/env python3
"""
=====================================================================
Stock-ZeroBaran — تعبئة بيانات تجريبية
المؤلف: Baran Avisat  |  Baranavisat@gmail.com  |  00905313263722
=====================================================================
يبني بيانات مبيعات وحركات مخزون تجريبية واقعية لاختبار النظام:
  • 8 منتجات في 4 تصنيفات
  • 90 يوماً من سجل المبيعات مع أنماط موسمية
  • أنماط اتجاه صعودي/هابطي
  • بعض المنتجات شارفت على النفاد لإثارة التنبيهات

التشغيل:
  python scripts/seed_sample_data.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from config.settings import get_settings, ensure_dirs
from src.utils.helpers import today_local, setup_logging

logger = setup_logging("INFO")


# ===================================================================
# بيانات المنتجات التجريبية
# ===================================================================
PRODUCTS = [
    {"id": "p001", "sku": "DRV-001", "name": "Olive Oil 1L", "category": "Food",
     "unit_cost": 4.5, "selling_price": 7.0, "reorder_point": 15, "reorder_qty": 60,
     "safety_stock": 8, "supplier_id": "s001"},
    {"id": "p002", "sku": "DRV-002", "name": "Basmati Rice 5kg", "category": "Food",
     "unit_cost": 8.0, "selling_price": 12.5, "reorder_point": 20, "reorder_qty": 80,
     "safety_stock": 10, "supplier_id": "s001"},
    {"id": "p003", "sku": "DRV-003", "name": "Lentils 1kg", "category": "Food",
     "unit_cost": 2.0, "selling_price": 3.5, "reorder_point": 25, "reorder_qty": 100,
     "safety_stock": 12, "supplier_id": "s002"},
    {"id": "p004", "sku": "DRV-004", "name": "Black Tea 500g", "category": "Beverages",
     "unit_cost": 3.0, "selling_price": 5.5, "reorder_point": 12, "reorder_qty": 50,
     "safety_stock": 6, "supplier_id": "s003"},
    {"id": "p005", "sku": "DRV-005", "name": "Honey 750g", "category": "Food",
     "unit_cost": 12.0, "selling_price": 20.0, "reorder_point": 8, "reorder_qty": 30,
     "safety_stock": 4, "supplier_id": "s004"},
    {"id": "p006", "sku": "DRV-006", "name": "Detergent 2L", "category": "Cleaning",
     "unit_cost": 3.5, "selling_price": 6.0, "reorder_point": 18, "reorder_qty": 70,
     "safety_stock": 9, "supplier_id": "s005"},
    {"id": "p007", "sku": "DRV-007", "name": "Sunflower Oil 1.5L", "category": "Food",
     "unit_cost": 4.0, "selling_price": 6.5, "reorder_point": 15, "reorder_qty": 60,
     "safety_stock": 8, "supplier_id": "s001"},
    {"id": "p008", "sku": "DRV-008", "name": "Coffee 200g", "category": "Beverages",
     "unit_cost": 5.0, "selling_price": 9.0, "reorder_point": 10, "reorder_qty": 40,
     "safety_stock": 5, "supplier_id": "s003"},
]


# ===================================================================
# أنماط المبيعات
# ===================================================================
def generate_sales_history(days: int = 90) -> pd.DataFrame:
    """يبني 90 يوماً من المبيعات بأنماط موسمية واقعية."""
    random.seed(42)
    rows = []
    today = today_local()
    start = today - timedelta(days=days)

    for d_offset in range(days):
        sale_date = start + timedelta(days=d_offset)
        weekday = sale_date.weekday()
        # تعزيز نهاية الأسبوع
        weekend_boost = 1.4 if weekday >= 5 else 1.0
        # نمط موسمي شهري (ذروة في الصيف للمشروبات)
        month = sale_date.month
        seasonal_factor = 1.2 if 6 <= month <= 8 else 1.0

        for p in PRODUCTS:
            # معدل قاعدي مختلف لكل منتج
            base_rate = {
                "p001": 2.5, "p002": 3.0, "p003": 1.8, "p004": 2.2,
                "p005": 0.7, "p006": 1.5, "p007": 2.8, "p008": 1.9,
            }[p["id"]]
            # اتجاه صعودي تدريجي
            trend = 1.0 + (d_offset / days) * 0.3
            # p005 (العسل) راكدة — معدل منخفض جداً
            if p["id"] == "p005":
                base_rate *= 0.15
            # p008 (القهوة) موسمية صيفية قوية
            if p["id"] == "p008":
                seasonal_factor = 1.5 if 6 <= month <= 8 else 1.0

            expected = base_rate * weekend_boost * seasonal_factor * trend
            # ضوضاء يومية
            qty = max(0, int(random.gauss(expected, expected * 0.3)))
            if qty == 0 and random.random() < 0.6:
                qty = 1
            rows.append({
                "product_id": p["id"],
                "sku": p["sku"],
                "name": p["name"],
                "quantity": qty,
                "unit_price": p["selling_price"],
                "sale_date": sale_date.isoformat(),
                "channel": "retail",
            })

    return pd.DataFrame(rows)


# ===================================================================
# التشغيل
# ===================================================================
def main() -> int:
    ensure_dirs()
    settings = get_settings()

    logger.info("🌱 بدء تعبئة البيانات التجريبية...")
    sales = generate_sales_history(days=90)
    csv_path = settings.data_dir / "sample_sales.csv"
    sales.to_csv(csv_path, index=False, encoding="utf-8")
    logger.info("💾 تم حفظ بيانات المبيعات في %s (%d سجل).", csv_path, len(sales))

    # عرض إحصائيات سريعة
    logger.info("📊 ملخّص المبيعات:")
    summary = sales.groupby("name")["quantity"].agg(["sum", "mean", "std"]).round(2)
    for name, row in summary.iterrows():
        print(f"  • {name:25s} — إجمالي {int(row['sum']):5d} | "
              f"متوسط {row['mean']:.1f}/يوم")

    # محاولة الدفع إلى Supabase (إن توفّر)
    try:
        from src.database.supabase_client import get_db
        db = get_db()
        if db.available:
            logger.info("📡 محاولة الدفع إلى Supabase...")
            # الموردين
            suppliers = [
                {"id": "s001", "name": "Mediterranean Foods Co.", "contact_email": "sales@medfoods.com",
                 "phone": "+90-531-100-2000", "lead_time_days": 7, "country": "Turkey"},
                {"id": "s002", "name": "Anatolian Grains Ltd.", "contact_email": "info@anatolian.com",
                 "phone": "+90-531-100-2001", "lead_time_days": 5, "country": "Turkey"},
                {"id": "s003", "name": "Beverage Distributors", "contact_email": "orders@bevdistrib.com",
                 "phone": "+90-531-100-2002", "lead_time_days": 3, "country": "Turkey"},
                {"id": "s004", "name": "Pure Honey Apiary", "contact_email": "info@purehoney.com",
                 "phone": "+90-531-100-2003", "lead_time_days": 10, "country": "Turkey"},
                {"id": "s005", "name": "CleanPro Supplies", "contact_email": "sales@cleanpro.com",
                 "phone": "+90-531-100-2004", "lead_time_days": 4, "country": "Turkey"},
            ]
            db.upsert("suppliers", suppliers, on_conflict="id")
            logger.info("✅ تم إدخال %d مورّداً.", len(suppliers))

            # المنتجات
            db.upsert("products", PRODUCTS, on_conflict="id")
            logger.info("✅ تم إدخال %d منتجاً.", len(PRODUCTS))

            # المبيعات (بكميات صغيرة لتجنّب تجاوز حدود الـ Free Tier)
            sales_records = []
            for _, r in sales.iterrows():
                sales_records.append({
                    "product_id": r["product_id"],
                    "quantity": float(r["quantity"]),
                    "unit_price": float(r["unit_price"]),
                    "sale_date": r["sale_date"],
                    "channel": r["channel"],
                })
            # دفع دفعات (batches)
            batch_size = 500
            for i in range(0, len(sales_records), batch_size):
                db.insert("sales", sales_records[i:i + batch_size])
            logger.info("✅ تم إدخال %d سجل مبيعات.", len(sales_records))
        else:
            logger.info("ℹ️ Supabase غير مُهيّأ — تم الحفظ محلياً فقط (وضع CSV).")
    except Exception as exc:
        logger.warning("تعذّر الدفع إلى Supabase (%s) — البيانات محفوظة محلياً.", exc)

    logger.info("✅ اكتملت تعبئة البيانات التجريبية.")
    logger.info("لتشغيل فحص المخزون: python scripts/run_inventory_check.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
