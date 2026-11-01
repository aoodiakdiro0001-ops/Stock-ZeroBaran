#!/usr/bin/env python3
"""
=====================================================================
Stock-ZeroBaran — السكريبت الرئيسي لفحص المخزون
المؤلف: Baran Avisat  |  Baranavisat@gmail.com  |  00905313263722
=====================================================================
يُشغّل دورياً عبر GitHub Actions كل صباح.

التسلسل:
  1) تحميل المنتجات والحركات من Supabase (أو CSV احتياطياً)
  2) حساب الكميات الحالية ومعدلات الاستهلاك
  3) تشغيل العقل التنبؤي (Gemini/Groq)
  4) إرسال التنبيهات الحرجة وتقرير الجرد عبر Telegram
  5) حفظ الحالة في Supabase

التشغيل اليدوي:
  python scripts/run_inventory_check.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

# ضمان وصول الاستيراد لجذر المشروع
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import PROJECT_META, ensure_dirs, get_settings
from src.core.alerts import AlertEngine
from src.core.forecasting import get_forecast_engine
from src.core.inventory import InventoryEngine
from src.utils.helpers import print_banner, report_header, setup_logging

logger = setup_logging()


def run() -> int:
    """ينفّذ دورة فحص كاملة."""
    print_banner()
    logger.info("▶️ بدء دورة فحص المخزون — Stock-ZeroBaran v%s",
                PROJECT_META["version"])

    ensure_dirs()
    settings = get_settings()

    try:
        # === 1) المراقبة والحسابات ===
        logger.info("━━━ الطبقة 1: المراقبة والحسابات ━━━")
        inv = InventoryEngine()
        snapshots = inv.snapshot()
        if not snapshots:
            logger.error("لا توجد لقطات مخزون. تأكّد من البيانات.")
            return 1
        inv.persist_stock_status(snapshots)

        critical = inv.critical_products(snapshots)
        low = inv.low_stock_products(snapshots)
        slow = inv.slow_moving_products(snapshots)
        logger.info("🔴 حرج: %d | 🟡 نقص: %d | 🔵 راكد: %d",
                     len(critical), len(low), len(slow))

        # === 2) التنبؤ بالذكاء الاصطناعي ===
        logger.info("━━━ الطبقة 2: العقل التنبؤي (AI) ━━━")
        fc_engine = get_forecast_engine()
        forecasts = fc_engine.forecast_all(snapshots)
        if forecasts:
            ai_count = sum(1 for f in forecasts if f.model_used != "fallback")
            logger.info("🤖 تم بناء %d تنبؤاً (%d عبر محرك لغوي).",
                         len(forecasts), ai_count)

            # حفظ التنبؤات في Supabase
            try:
                from src.database.supabase_client import get_db
                db = get_db()
                if db.available:
                    rows = [{
                        "product_id": f.product_id,
                        "forecast_date": f.forecast_date,
                        "expected_demand": f.expected_demand,
                        "confidence": f.confidence,
                        "suggested_reorder": f.suggested_reorder,
                        "model_used": f.model_used,
                        "reasoning": f.reasoning[:1000],
                    } for f in forecasts]
                    db.insert("forecasts", rows)
                    logger.info("💾 تم حفظ التنبؤات في Supabase.")
            except Exception as exc:
                logger.warning("تعذّر حفظ التنبؤات في قاعدة البيانات: %s", exc)

        # === 3) إرسال التنبيهات والتقارير ===
        logger.info("━━━ الطبقة 3: التوصيل والتنبيه ━━━")
        alert_engine = AlertEngine()
        sent_critical = alert_engine.dispatch_critical_alerts(snapshots, forecasts)
        sent_low = alert_engine.dispatch_low_stock_alerts(snapshots)
        sent_slow = alert_engine.dispatch_slow_moving_alerts(snapshots)
        alert_engine.dispatch_daily_report(snapshots, forecasts)

        logger.info("📬 تم إرسال: %d حرج + %d نقص + %d راكد.",
                     sent_critical, sent_low, sent_slow)

        # === 4) تلخيص نهائي ===
        logger.info("━━━ التقرير النهائي ━━━")
        print()
        print(report_header("ملخّص دورة الفحص"))
        print(f"  • إجمالي المنتجات المعالَجة: {len(snapshots)}")
        print(f"  • 🔴 منتجات حرجة: {len(critical)}")
        print(f"  • 🟡 منتجات نقص: {len(low)}")
        print(f"  • 🔵 منتجات راكدة: {len(slow)}")
        print(f"  • 🤖 تنبؤات AI: {len(forecasts)}")
        print(f"  • 📬 تنبيهات مُرسلة: {sent_critical + sent_low + sent_slow}")
        print(f"  • 🕒 {settings.TIMEZONE}")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()

        return 0

    except Exception as exc:
        logger.error("فشل دورة الفحص: %s", exc)
        logger.debug(traceback.format_exc())
        return 2


if __name__ == "__main__":
    sys.exit(run())
