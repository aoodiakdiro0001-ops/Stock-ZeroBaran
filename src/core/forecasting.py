"""
=====================================================================
Stock-ZeroBaran — العقل التنبؤي والذكاء الاصطناعي (AI Forecasting Core)
المؤلف: Baran Avisat  |  Baranavisat@gmail.com  |  00905313263722
=====================================================================
يستخدم Google Gemini API (أو Groq كبديل) لـ:
  • تحليل الأنماط التاريخية للمبيعات
  • التنبؤ بالطلب المستقبلي
  • اقتراح كمية إعادة الطلب المثالية
  • اكتشاف السلع الراكدة
  • رصد الأنماط الموسمية
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from config.settings import get_settings
from src.core.inventory import StockSnapshot
from src.utils.helpers import today_local, days_ago, load_sample_sales

logger = logging.getLogger("stockzerobaran.forecasting")

settings = get_settings()


# ===================================================================
# نموذج التنبؤ
# ===================================================================
@dataclass
class DemandForecast:
    """نتيجة التنبؤ بمنتج واحد."""
    product_id: str
    sku: str
    name: str
    forecast_date: str
    expected_demand: float
    confidence: float
    suggested_reorder: float
    days_until_stockout: Optional[float]
    model_used: str
    reasoning: str
    seasonal_note: str
    is_slow_moving: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ===================================================================
# بناء موجز المنتج للذكاء الاصطناعي
# ===================================================================
def _build_product_context(snap: StockSnapshot, history: pd.DataFrame,
                            horizon: int) -> str:
    """يبني سياقاً نصياً للمنتج يُرسل للنموذج اللغوي."""
    if not history.empty:
        recent = history.tail(30)
        daily_avg = recent["quantity"].mean() if not recent.empty else 0
        trend = (recent.tail(7)["quantity"].mean()
                 - recent.head(7)["quantity"].mean()) if len(recent) >= 14 else 0
        max_qty = history["quantity"].max()
        min_qty = history["quantity"].min()
        series_sample = history.tail(14)[["sale_date", "quantity"]].to_dict("records")
        series_str = "\n".join(
            f"  - {r['sale_date']}: {r['quantity']:.1f} وحدة" for r in series_sample
        )
    else:
        daily_avg = trend = max_qty = min_qty = 0
        series_str = "  (لا توجد بيانات تاريخية كافية)"

    return f"""
منتج: {snap.name} (SKU: {snap.sku})
التصنيف: {snap.category}
المخزون الحالي: {snap.current_stock:.1f} وحدة
معدل الاستهلاك اليومي: {snap.daily_consumption_rate:.2f} وحدة/يوم
الأيام المتبقية حتى النفاد: {snap.days_until_stockout}
نقطة إعادة الطلب الحالية: {snap.reorder_point}
كمية إعادة الطلب الافتراضية: {snap.reorder_qty}
مخزون الأمان: {snap.safety_stock}
تكلفة الوحدة: {snap.unit_cost} | سعر البيع: {snap.selling_price}
آخر 14 يوماً من المبيعات:
{series_str}

المتوسط اليومي (30 يوماً): {daily_avg:.2f}
الاتجاه (الفرق بين آخر أسبوع وأول أسبوع): {trend:+.2f}
أعلى كمية يومية: {max_qty} | أدنى كمية يومية: {min_qty}

المطلوب: توقّع الطلب خلال الـ {horizon} يوماً القادمة، واقترح كمية إعادة الطلب المثالية
بما يأخذ بعين الاعتبار المواسم، زمن التوريد، وتجنّب النفاد والركود.
"""


# ===================================================================
# تحليل استجابة النموذج اللغوي
# ===================================================================
def _parse_ai_response(text: str, snap: StockSnapshot,
                       horizon: int, model: str) -> DemandForecast:
    """يستخرج الأرقام والتفسير من استجابة النموذج اللغوي."""
    expected_demand = snap.daily_consumption_rate * horizon
    confidence = 70.0
    suggested_reorder = float(snap.reorder_qty)
    seasonal_note = ""
    reasoning = text[:500]

    try:
        # محاولة استخراج JSON إن وُجد
        import re
        json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
            expected_demand = float(parsed.get("expected_demand", expected_demand))
            confidence = float(parsed.get("confidence", confidence))
            suggested_reorder = float(parsed.get("suggested_reorder", suggested_reorder))
            seasonal_note = parsed.get("seasonal_note", "")
            reasoning = parsed.get("reasoning", reasoning)
    except Exception:
        # استخراج بالأرقام
        import re
        nums = re.findall(r"[-+]?\d*\.?\d+", text)
        if nums:
            try:
                expected_demand = float(nums[0])
                if len(nums) > 1:
                    suggested_reorder = float(nums[1])
                if len(nums) > 2:
                    confidence = max(0.0, min(100.0, float(nums[2])))
            except ValueError:
                pass

    is_slow = (snap.daily_consumption_rate > 0
               and snap.days_until_stockout is not None
               and snap.days_until_stockout > 60)

    return DemandForecast(
        product_id=snap.product_id,
        sku=snap.sku,
        name=snap.name,
        forecast_date=today_local().isoformat(),
        expected_demand=round(expected_demand, 2),
        confidence=round(confidence, 2),
        suggested_reorder=round(suggested_reorder, 2),
        days_until_stockout=snap.days_until_stockout,
        model_used=model,
        reasoning=reasoning.strip(),
        seasonal_note=seasonal_note.strip(),
        is_slow_moving=is_slow,
    )


# ===================================================================
# محرّك التنبؤ
# ===================================================================
class ForecastingEngine:
    """يبني تنبؤات الطلب باستخدام Gemini أو Groq."""

    def __init__(self, engine: Optional[str] = None) -> None:
        self.engine = (engine or settings.AI_ENGINE).lower()
        self._gemini_model = None
        self._groq_client = None

    # ------------------------------------------------------------------
    def _init_gemini(self) -> bool:
        if self._gemini_model is not None:
            return True
        if not settings.GEMINI_API_KEY or "your-" in settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY غير مُهيّأ.")
            return False
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._gemini_model = genai.GenerativeModel("gemini-1.5-flash")
            logger.info("✅ تم تهيئة Gemini API.")
            return True
        except Exception as exc:
            logger.error("فشل تهيئة Gemini: %s", exc)
            return False

    def _init_groq(self) -> bool:
        if self._groq_client is not None:
            return True
        if not settings.GROQ_API_KEY or "your-" in settings.GROQ_API_KEY:
            logger.warning("GROQ_API_KEY غير مُهيّأ.")
            return False
        try:
            from groq import Groq
            self._groq_client = Groq(api_key=settings.GROQ_API_KEY)
            logger.info("✅ تم تهيئة Groq API.")
            return True
        except Exception as exc:
            logger.error("فشل تهيئة Groq: %s", exc)
            return False

    # ------------------------------------------------------------------
    def _call_gemini(self, prompt: str) -> str:
        if not self._init_gemini():
            return ""
        try:
            response = self._gemini_model.generate_content(prompt)
            return response.text or ""
        except Exception as exc:
            logger.error("فشل استدعاء Gemini: %s", exc)
            return ""

    def _call_groq(self, prompt: str) -> str:
        if not self._init_groq():
            return ""
        try:
            completion = self._groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": (
                        "أنت محلل سلاسل توريد خبير. أجب بدقة واقتصاد، "
                        "وقدّم رقماً واضحاً للطلب المتوقع وكمية إعادة الطلب."
                    )},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=600,
            )
            return completion.choices[0].message.content or ""
        except Exception as exc:
            logger.error("فشل استدعاء Groq: %s", exc)
            return ""

    # ------------------------------------------------------------------
    def _call_ai(self, prompt: str) -> Tuple[str, str]:
        """يستدعي المحرك المختار ويُرجع (النص، اسم_المحرك)."""
        if self.engine == "gemini":
            txt = self._call_gemini(prompt)
            if txt:
                return txt, "gemini"
            # محاولة Groq كبديل
            logger.info("التبديل إلى Groq كبديل لـ Gemini.")
            txt = self._call_groq(prompt)
            return txt, "groq" if txt else "fallback"
        elif self.engine == "groq":
            txt = self._call_groq(prompt)
            if txt:
                return txt, "groq"
            logger.info("التبديل إلى Gemini كبديل لـ Groq.")
            txt = self._call_gemini(prompt)
            return txt, "gemini" if txt else "fallback"
        # محرّك غير معروف — استخدم الحساب الإحصائي
        return "", "fallback"

    # ------------------------------------------------------------------
    # التنبؤ بمنتج واحد
    # ------------------------------------------------------------------
    def forecast_product(self, snap: StockSnapshot,
                          sales_history: Optional[pd.DataFrame] = None,
                          horizon: Optional[int] = None) -> DemandForecast:
        horizon = horizon or settings.FORECAST_HORIZON_DAYS
        if sales_history is None:
            sales_history = self._load_history(snap.product_id)

        ctx = _build_product_context(snap, sales_history, horizon)
        prompt = f"""أنت محلل بيانات متخصص في سلاسل التوريد وإدارة المخزون.
حلّل بيانات المنتج التالية وقدّم تنبؤك خلال الـ {horizon} يوماً القادمة.

{ctx}

أجب بصيغة JSON بالضبط بالشكل التالي (بدون شرح إضافي قبل أو بعد الـ JSON):
{{
  "expected_demand": <رقم>,
  "confidence": <رقم بين 0 و100>,
  "suggested_reorder": <رقم>,
  "seasonal_note": "<ملاحظة موسمية قصيرة>",
  "reasoning": "<شرح موجز بالعربية>"
}}
"""
        text, model_used = self._call_ai(prompt)
        if not text:
            # حساب احتياطي إحصائي
            expected = snap.daily_consumption_rate * horizon
            suggested = max(float(snap.reorder_qty),
                            expected - snap.current_stock + snap.safety_stock)
            text = json.dumps({
                "expected_demand": round(expected, 2),
                "confidence": 60.0,
                "suggested_reorder": round(suggested, 2),
                "seasonal_note": "لا توجد بيانات موسمية كافية",
                "reasoning": "تنبؤ إحصائي بديل — المحرك اللغوي غير متاح.",
            }, ensure_ascii=False)
            model_used = "fallback"

        return _parse_ai_response(text, snap, horizon, model_used)

    # ------------------------------------------------------------------
    def forecast_all(self, snapshots: List[StockSnapshot],
                      horizon: Optional[int] = None) -> List[DemandForecast]:
        """يبني تنبؤات لكل المنتجات."""
        results: List[DemandForecast] = []
        for snap in snapshots:
            try:
                fc = self.forecast_product(snap, horizon=horizon)
                results.append(fc)
            except Exception as exc:
                logger.error("فشل التنبؤ لـ %s: %s", snap.sku, exc)
        logger.info("تم بناء %d تنبؤاً.", len(results))
        return results

    # ------------------------------------------------------------------
    def _load_history(self, product_id: str) -> pd.DataFrame:
        """يحمّل تاريخ المبيعات لمنتج."""
        sales = load_sample_sales()
        if sales.empty:
            return sales
        sales = sales[sales["product_id"] == product_id].copy()
        sales["sale_date"] = pd.to_datetime(sales["sale_date"])
        sales = sales.sort_values("sale_date")
        return sales.tail(settings.FORECAST_HISTORY_DAYS)

    # ------------------------------------------------------------------
    # رصد الأنماط الموسمية
    # ------------------------------------------------------------------
    def detect_seasonality(self, sales: pd.DataFrame) -> Dict[str, Any]:
        """يكتشف أنماط موسمية بسيطة من بيانات المبيعات."""
        if sales.empty or "sale_date" not in sales.columns:
            return {"has_pattern": False}
        df = sales.copy()
        df["sale_date"] = pd.to_datetime(df["sale_date"])
        df["weekday"] = df["sale_date"].dt.day_name()
        df["month"] = df["sale_date"].dt.month
        by_weekday = df.groupby("weekday")["quantity"].mean().to_dict()
        by_month = df.groupby("month")["quantity"].mean().to_dict()
        return {
            "has_pattern": True,
            "weekday_pattern": by_weekday,
            "monthly_pattern": by_month,
            "peak_weekday": max(by_weekday, key=by_weekday.get) if by_weekday else None,
            "peak_month": max(by_month, key=by_month.get) if by_month else None,
        }


# ===================================================================
# نقطة وصول موحّدة
# ===================================================================
_forecast_engine: Optional[ForecastingEngine] = None


def get_forecast_engine() -> ForecastingEngine:
    global _forecast_engine
    if _forecast_engine is None:
        _forecast_engine = ForecastingEngine()
    return _forecast_engine


# استيراد مؤجّل لتجنّب الاستيراد الدائري
from typing import Tuple  # noqa: E402
