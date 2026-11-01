"""
=====================================================================
Stock-ZeroBaran — وظائف مساعدة عامة
المؤلف: Baran Avisat  |  Baranavisat@gmail.com  |  00905313263722
=====================================================================
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from pytz import timezone

from config.settings import PROJECT_ROOT, get_settings, PROJECT_META

# --------------------------------------------------------------------
# إعداد التسجيل (Logging)
# --------------------------------------------------------------------
def setup_logging(level: Optional[str] = None) -> logging.Logger:
    """يُهيّئ التسجيل الملوّن للنظام."""
    try:
        from colorlog import ColoredFormatter
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            ColoredFormatter(
                "%(log_color)s%(asctime)s │ %(name)-22s │ %(levelname)-8s │ %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "bold_red",
                },
            )
        )
    except ImportError:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s │ %(name)s │ %(levelname)s │ %(message)s",
                              datefmt="%Y-%m-%d %H:%M:%S")
        )

    root = logging.getLogger()
    root.setLevel(level or get_settings().LOG_LEVEL)
    root.handlers.clear()
    root.addHandler(handler)

    # ملف سجل
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "stockzerobaran.log", encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s │ %(name)s │ %(levelname)s │ %(message)s")
    )
    root.addHandler(file_handler)

    return logging.getLogger("stockzerobaran")


# --------------------------------------------------------------------
# التواريخ والمنطقة الزمنية
# --------------------------------------------------------------------
def now_local() -> datetime:
    """الوقت الحالي بالمنطقة الزمنية المُهيّأة."""
    s = get_settings()
    try:
        tz = timezone(s.TIMEZONE)
        return datetime.now(tz)
    except Exception:
        return datetime.utcnow()


def today_local() -> date:
    return now_local().date()


def days_ago(n: int) -> date:
    return today_local() - timedelta(days=n)


# --------------------------------------------------------------------
# لافتة المشروع (Banner)
# --------------------------------------------------------------------
BANNER = r"""
=====================================================================
   ███████ ███    ██  ██████  ██   ██ ███████ ███████ ███████
   ██      ████   ██ ██       ██  ██  ██      ██      ██
   █████   ██ ██  ██ ██   ███ █████   █████   █████   ███████
   ██      ██  ██ ██ ██    ██ ██  ██  ██      ██           ██
   ███████ ██   ████  ██████  ██   ██ ███████ ███████ ███████
              Zero-Barcode Smart Inventory & Demand Forecasting
=====================================================================
  المؤلف: Baran Avisat  |  Baranavisat@gmail.com  |  00905313263722
  الإصدار: {version}  |  Stack: Python · Supabase · Gemini · Streamlit
=====================================================================
""".format(version=PROJECT_META["version"])


def print_banner() -> None:
    print(BANNER)


# --------------------------------------------------------------------
# أدوات Pandas
# --------------------------------------------------------------------
def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """قسمة آمنة تتجنّب القسمة على صفر."""
    return numerator / denominator if denominator else default


def classification_health(days_left: Optional[float], current_stock: float,
                          critical_days: int, safety_stock: int,
                          reorder_point: int) -> str:
    """تصنيف صحة المخزون بناءً على الأيام المتبقية والكمية."""
    if current_stock <= 0:
        return "out"
    if days_left is not None and days_left <= critical_days:
        return "critical"
    if current_stock <= safety_stock:
        return "critical"
    if current_stock <= reorder_point:
        return "low"
    if days_left is not None and days_left > 60 and current_stock > reorder_point * 3:
        return "overstock"
    return "healthy"


# --------------------------------------------------------------------
# تنسيق العملة والأرقام
# --------------------------------------------------------------------
def fmt_money(value: float, currency: str = "$") -> str:
    """تنسيق مبلغ مالي بشكل مقروء."""
    try:
        return f"{currency}{value:,.2f}"
    except Exception:
        return f"{currency}0.00"


def fmt_qty(value: float) -> str:
    """تنسيق كمية (قطعة/كجم)."""
    try:
        if value == int(value):
            return f"{int(value):,}"
        return f"{value:,.2f}"
    except Exception:
        return "0"


# --------------------------------------------------------------------
# تحميل بيانات مبيعات تجريبية
# --------------------------------------------------------------------
def load_sample_sales() -> pd.DataFrame:
    """يحمّل بيانات المبيعات التجريبية من CSV."""
    s = get_settings()
    if not s.sample_sales_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(s.sample_sales_path, parse_dates=["sale_date"])
    return df


# --------------------------------------------------------------------
# شعار مدمج للتقارير
# --------------------------------------------------------------------
def report_header(title: str) -> str:
    ts = now_local().strftime("%Y-%m-%d %H:%M %Z")
    return (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  Stock-ZeroBaran │ {title}\n"
        f"  التاريخ: {ts}\n"
        f"  المؤلف: Baran Avisat — Baranavisat@gmail.com\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
