"""
=====================================================================
Stock-ZeroBaran — طبقة التوصيل والتنبيه (Reporting & Delivery Layer)
المؤلف: Baran Avisat  |  Baranavisat@gmail.com  |  00905313263722
=====================================================================
يرسل تنبيهات ذكية عبر Telegram Bot API:
  • تنبيهات المخزون الحرج (قبل النفاد)
  • تنبيهات نقص المخزون
  • اقتراحات إعادة الطلب
  • اكتشاف السلع الراكدة
  • تقرير الجرد اليومي
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import requests

from config.settings import get_settings
from src.core.forecasting import DemandForecast
from src.core.inventory import StockSnapshot
from src.database.supabase_client import get_db
from src.utils.helpers import fmt_money, fmt_qty, today_local, now_local

logger = logging.getLogger("stockzerobaran.alerts")
settings = get_settings()

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


# ===================================================================
# تنسيق الرسائل
# ===================================================================
def _emoji_for_health(health: str) -> str:
    return {
        "healthy": "🟢",
        "low": "🟡",
        "critical": "🔴",
        "out": "⚫",
        "overstock": "🔵",
    }.get(health, "⚪")


def format_stockout_alert(snap: StockSnapshot, forecast: Optional[DemandForecast] = None) -> str:
    """تنسيق تنبيه مخزون حرج."""
    days_str = f"{snap.days_until_stockout:.0f}" if snap.days_until_stockout is not None else "—"
    suggested = forecast.suggested_reorder if forecast else snap.reorder_qty
    reasoning = (forecast.reasoning[:200] + "…") if forecast and len(forecast.reasoning) > 200 \
        else (forecast.reasoning if forecast else "")
    seasonal = forecast.seasonal_note if forecast else ""

    msg = (
        f"🔴 <b>تنبيه مخزون حرج</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>المنتج:</b> {snap.name}\n"
        f"🔖 <b>SKU:</b> {snap.sku}\n"
        f"🏷️ <b>التصنيف:</b> {snap.category}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>المتبقي:</b> {fmt_qty(snap.current_stock)} وحدة\n"
        f"⚡ <b>معدل الاستهلاك:</b> {snap.daily_consumption_rate:.2f} وحدة/يوم\n"
        f"⏳ <b>سينفد خلال:</b> {days_str} يوم\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 <b>الكمية المقترحة لإعادة الطلب:</b> {fmt_qty(suggested)} وحدة\n"
    )
    if reasoning:
        msg += f"💡 <b>التفسير:</b> {reasoning}\n"
    if seasonal:
        msg += f"📅 <b>موسمي:</b> {seasonal}\n"
    msg += (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏢 <b>المورّد:</b> {snap.supplier_name}\n"
        f"🕒 {now_local().strftime('%Y-%m-%d %H:%M')}\n"
        f"<i>Stock-ZeroBaran</i>"
    )
    return msg


def format_low_stock_alert(snap: StockSnapshot) -> str:
    """تنسيق تنبيه نقص مخزون."""
    days_str = f"{snap.days_until_stockout:.0f}" if snap.days_until_stockout is not None else "—"
    return (
        f"🟡 <b>تنبيه نقص مخزون</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 {snap.name} ({snap.sku})\n"
        f"📊 المتبقي: {fmt_qty(snap.current_stock)} وحدة\n"
        f"🎯 نقطة إعادة الطلب: {snap.reorder_point}\n"
        f"⏳ سينفد خلال: {days_str} يوم\n"
        f"🛒 كمية إعادة الطلب الافتراضية: {fmt_qty(snap.reorder_qty)} وحدة\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Stock-ZeroBaran</i>"
    )


def format_slow_moving_alert(snap: StockSnapshot) -> str:
    """تنسيق تنبيه سلعة راكدة."""
    return (
        f"🔵 <b>تنبيه سلعة راكدة</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 {snap.name} ({snap.sku})\n"
        f"📊 المخزون الحالي: {fmt_qty(snap.current_stock)} وحدة\n"
        f"⚡ معدل الاستهلاك اليومي: {snap.daily_consumption_rate:.2f}\n"
        f"⏳ سيستغرق {snap.days_until_stockout:.0f} يوماً للنفاد بالوتيرة الحالية\n"
        f"💡 يُنصح بمراجعة استراتيجية التسعير أو العروض الترويجية\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Stock-ZeroBaran</i>"
    )


def format_daily_report(snapshots: List[StockSnapshot],
                         forecasts: List[DemandForecast]) -> str:
    """تنسيق التقرير اليومي للجرد."""
    total = len(snapshots)
    critical = [s for s in snapshots if s.stock_health in ("critical", "out")]
    low = [s for s in snapshots if s.stock_health == "low"]
    slow = [s for s in snapshots if s.stock_health == "overstock"]
    healthy = [s for s in snapshots if s.stock_health == "healthy"]
    inventory_value = sum(s.current_stock * s.unit_cost for s in snapshots)
    potential_revenue = sum(s.current_stock * s.selling_price for s in snapshots)

    msg = (
        f"📊 <b>تقرير الجرد اليومي</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 {today_local().strftime('%Y-%m-%d')}\n\n"
        f"📈 <b>ملخّص عام:</b>\n"
        f"• إجمالي المنتجات: {total}\n"
        f"• 🟢 سليم: {len(healthy)}\n"
        f"• 🟡 نقص مخزون: {len(low)}\n"
        f"• 🔴 حرج: {len(critical)}\n"
        f"• 🔵 راكد: {len(slow)}\n\n"
        f"💰 <b>قيمة المخزون:</b> {fmt_money(inventory_value)}\n"
        f"💵 <b>الإيراد المحتمل:</b> {fmt_money(potential_revenue)}\n"
    )

    if critical:
        msg += f"\n━━━━━━━━━━━━━━━━━━━━━\n🔴 <b>منتجات حرجة ({len(critical)}):</b>\n"
        for s in critical[:5]:
            days_str = f"{s.days_until_stockout:.0f}" if s.days_until_stockout else "—"
            msg += f"• {s.name} — متبقي {fmt_qty(s.current_stock)} ({days_str} يوم)\n"
        if len(critical) > 5:
            msg += f"• …و {len(critical) - 5} منتج آخر\n"

    if forecasts:
        ai_active = sum(1 for f in forecasts if f.model_used != "fallback")
        msg += (
            f"\n━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <b>الذكاء الاصطناعي:</b>\n"
            f"• تنبؤات نُفّذت: {len(forecasts)}\n"
            f"• عبر محرك لغوي: {ai_active}\n"
            f"• تنبؤات إحصائية احتياطية: {len(forecasts) - ai_active}\n"
        )

    msg += (
        f"\n━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Stock-ZeroBaran — المنظومة الذاتية الذكية</i>\n"
        f"<i>المؤلف: Baran Avisat</i>"
    )
    return msg


# ===================================================================
# محرّك التنبيهات
# ===================================================================
class AlertEngine:
    """يرسل التنبيهات عبر تليجرام ويُسجّلها في قاعدة البيانات."""

    def __init__(self) -> None:
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.enabled = (
            settings.ALERTS_ENABLED
            and bool(self.token) and bool(self.chat_id)
            and "your-" not in str(self.token)
            and "your-" not in str(self.chat_id)
        )
        if self.enabled:
            logger.info("✅ تنبيهات Telegram مُفعّلة.")
        else:
            logger.info("تنبيهات Telegram غير مُفعّلة (تحقّق من .env).")

    # ------------------------------------------------------------------
    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """يرسل رسالة عبر Telegram Bot API."""
        if not self.enabled:
            logger.info("[محاكاة] رسالة تليجرام: %s", message[:80].replace("\n", " "))
            return True
        try:
            url = TELEGRAM_API.format(token=self.token)
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            }
            response = requests.post(url, json=payload, timeout=15)
            if response.status_code == 200:
                logger.info("✅ تم إرسال رسالة تليجرام.")
                return True
            logger.error("فشل تليجرام %d: %s", response.status_code, response.text[:200])
            return False
        except Exception as exc:
            logger.error("استثناء أثناء إرسال تليجرام: %s", exc)
            return False

    # ------------------------------------------------------------------
    def log_alert(self, product_id: Optional[str], alert_type: str, message: str,
                   severity: str = "info", suggested_qty: Optional[float] = None,
                   days_left: Optional[float] = None) -> None:
        """يسجّل التنبيه في جدول alerts_log."""
        db = get_db()
        if not db.available:
            return
        row = {
            "product_id": product_id,
            "alert_type": alert_type,
            "severity": severity,
            "message": message[:1000],
            "suggested_qty": suggested_qty,
            "days_left": days_left,
            "channel": "telegram",
            "sent_at": "now()",
        }
        try:
            db.insert("alerts_log", [row])
        except Exception as exc:
            logger.error("فشل تسجيل التنبيه: %s", exc)

    # ------------------------------------------------------------------
    # إرسال تنبيهات بناءً على اللقطات والتنبؤات
    # ------------------------------------------------------------------
    def dispatch_critical_alerts(self, snapshots: List[StockSnapshot],
                                  forecasts: List[DemandForecast]) -> int:
        """يرسل تنبيهات للمنتجات الحرجة فقط."""
        fc_map = {f.product_id: f for f in forecasts}
        critical = [s for s in snapshots if s.stock_health in ("critical", "out")]
        sent = 0
        for snap in critical:
            fc = fc_map.get(snap.product_id)
            msg = format_stockout_alert(snap, fc)
            if self.send(msg):
                sent += 1
                self.log_alert(
                    product_id=snap.product_id,
                    alert_type="stockout_critical",
                    message=msg,
                    severity="critical",
                    suggested_qty=fc.suggested_reorder if fc else snap.reorder_qty,
                    days_left=snap.days_until_stockout,
                )
        logger.info("أُرسل %d تنبيه حرج.", sent)
        return sent

    def dispatch_low_stock_alerts(self, snapshots: List[StockSnapshot]) -> int:
        """يرسل تنبيهات نقص المخزون."""
        low = [s for s in snapshots if s.stock_health == "low"]
        sent = 0
        for snap in low:
            msg = format_low_stock_alert(snap)
            if self.send(msg):
                sent += 1
                self.log_alert(
                    product_id=snap.product_id,
                    alert_type="low_stock",
                    message=msg,
                    severity="warning",
                    suggested_qty=snap.reorder_qty,
                    days_left=snap.days_until_stockout,
                )
        logger.info("أُرسل %d تنبيه نقص.", sent)
        return sent

    def dispatch_slow_moving_alerts(self, snapshots: List[StockSnapshot]) -> int:
        """يرسل تنبيهات السلع الراكدة."""
        slow = [s for s in snapshots if s.stock_health == "overstock"]
        sent = 0
        for snap in slow:
            msg = format_slow_moving_alert(snap)
            if self.send(msg):
                sent += 1
                self.log_alert(
                    product_id=snap.product_id,
                    alert_type="slow_moving",
                    message=msg,
                    severity="info",
                    days_left=snap.days_until_stockout,
                )
        return sent

    # ------------------------------------------------------------------
    def dispatch_daily_report(self, snapshots: List[StockSnapshot],
                              forecasts: List[DemandForecast]) -> bool:
        """يرسل التقرير اليومي."""
        msg = format_daily_report(snapshots, forecasts)
        ok = self.send(msg)
        if ok:
            self.log_alert(
                product_id=None,
                alert_type="daily_report",
                message=msg,
                severity="info",
            )
        return ok
