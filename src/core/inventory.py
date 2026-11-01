"""
=====================================================================
Stock-ZeroBaran — طبقة المراقبة والحسابات (Tracking & Calculation Layer)
المؤلف: Baran Avisat  |  Baranavisat@gmail.com  |  00905313263722
=====================================================================
يحسب الكميات الحالية، معدلات الاستهلاك اليومية، الأيام المتبقية
حتى النفاد، ويصنّف صحة المخزون باستخدام Pandas.

آلية العمل:
  1) يجمع حركات الوارد والصادر من قاعدة البيانات (أو CSV عند عدم توفّرها)
  2) يحسب المخزون الحالي = مجموع الوارد - مجموع الصادر
  3) يحسب معدل الاستهلاك اليومي عبر نافذة زمنية (افتراضياً 30 يوماً)
  4) يحسب الأيام المتبقية حتى النفاد = المخزون الحالي ÷ معدل الاستهلاك
  5) يصنّف الصحة: healthy / low / critical / out / overstock
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config.settings import get_settings
from src.database.supabase_client import SupabaseClient, get_db
from src.utils.helpers import (
    days_ago, today_local, safe_div, classification_health,
    load_sample_sales,
)

logger = logging.getLogger("stockzerobaran.inventory")

settings = get_settings()


# ===================================================================
# نماذج البيانات
# ===================================================================
@dataclass
class StockSnapshot:
    """لقطة لحالة مخزون منتج واحد."""
    product_id: str
    sku: str
    name: str
    category: str
    current_stock: float
    daily_consumption_rate: float
    days_until_stockout: Optional[float]
    reorder_point: int
    reorder_qty: int
    safety_stock: int
    unit_cost: float
    selling_price: float
    stock_health: str
    last_movement_date: Optional[str]
    supplier_name: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ===================================================================
# محرك المخزون
# ===================================================================
class InventoryEngine:
    """المحرك الذي يحسب حالة المخزون ويحدّثها."""

    def __init__(self, db: Optional[SupabaseClient] = None) -> None:
        self.db = db or get_db()
        self._products_cache: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # تحميل المنتجات
    # ------------------------------------------------------------------
    def load_products(self) -> pd.DataFrame:
        """يحمّل كتالوج المنتجات كـ DataFrame."""
        if self._products_cache is not None:
            return self._products_cache

        if self.db.available:
            try:
                products = self.db.select("products", filters={"is_active": True})
                suppliers = self.db.select("suppliers")
                suppliers_map = {s["id"]: s["name"] for s in suppliers}
                for p in products:
                    p["supplier_name"] = suppliers_map.get(p.get("supplier_id"), "—")
                df = pd.DataFrame(products)
                self._products_cache = df
                return df
            except Exception as exc:
                logger.warning("تعذّر تحميل المنتجات من Supabase (%s) — استخدام CSV.", exc)

        # وضع محلي احتياطي
        df = self._load_local_products()
        self._products_cache = df
        return df

    def _load_local_products(self) -> pd.DataFrame:
        """يولّد كتالوج منتجات تجريبي عند عدم توفّر Supabase."""
        local_data = [
            {"id": "p001", "sku": "DRV-001", "name": "Olive Oil 1L", "name_ar": "زيت زيتون 1ل",
             "category": "Food", "unit": "piece", "unit_cost": 4.5, "selling_price": 7.0,
             "reorder_point": 15, "reorder_qty": 60, "safety_stock": 8, "supplier_id": None,
             "supplier_name": "Local Supplier A"},
            {"id": "p002", "sku": "DRV-002", "name": "Basmati Rice 5kg", "name_ar": "رز بسمتي 5كغ",
             "category": "Food", "unit": "piece", "unit_cost": 8.0, "selling_price": 12.5,
             "reorder_point": 20, "reorder_qty": 80, "safety_stock": 10, "supplier_id": None,
             "supplier_name": "Local Supplier B"},
            {"id": "p003", "sku": "DRV-003", "name": "Lentils 1kg", "name_ar": "عدس 1كغ",
             "category": "Food", "unit": "piece", "unit_cost": 2.0, "selling_price": 3.5,
             "reorder_point": 25, "reorder_qty": 100, "safety_stock": 12, "supplier_id": None,
             "supplier_name": "Local Supplier A"},
            {"id": "p004", "sku": "DRV-004", "name": "Black Tea 500g", "name_ar": "شاي أسود 500غ",
             "category": "Beverages", "unit": "piece", "unit_cost": 3.0, "selling_price": 5.5,
             "reorder_point": 12, "reorder_qty": 50, "safety_stock": 6, "supplier_id": None,
             "supplier_name": "Local Supplier C"},
            {"id": "p005", "sku": "DRV-005", "name": "Honey 750g", "name_ar": "عسل 750غ",
             "category": "Food", "unit": "piece", "unit_cost": 12.0, "selling_price": 20.0,
             "reorder_point": 8, "reorder_qty": 30, "safety_stock": 4, "supplier_id": None,
             "supplier_name": "Local Supplier D"},
            {"id": "p006", "sku": "DRV-006", "name": "Detergent 2L", "name_ar": "منظف 2ل",
             "category": "Cleaning", "unit": "piece", "unit_cost": 3.5, "selling_price": 6.0,
             "reorder_point": 18, "reorder_qty": 70, "safety_stock": 9, "supplier_id": None,
             "supplier_name": "Local Supplier E"},
            {"id": "p007", "sku": "DRV-007", "name": "Sunflower Oil 1.5L", "name_ar": "زيت دوار الشمس 1.5ل",
             "category": "Food", "unit": "piece", "unit_cost": 4.0, "selling_price": 6.5,
             "reorder_point": 15, "reorder_qty": 60, "safety_stock": 8, "supplier_id": None,
             "supplier_name": "Local Supplier A"},
            {"id": "p008", "sku": "DRV-008", "name": "Coffee 200g", "name_ar": "قهوة 200غ",
             "category": "Beverages", "unit": "piece", "unit_cost": 5.0, "selling_price": 9.0,
             "reorder_point": 10, "reorder_qty": 40, "safety_stock": 5, "supplier_id": None,
             "supplier_name": "Local Supplier C"},
        ]
        return pd.DataFrame(local_data)

    # ------------------------------------------------------------------
    # تحميل حركات المخزون
    # ------------------------------------------------------------------
    def load_movements(self, days: int = 90) -> pd.DataFrame:
        """يحمّل حركات الوارد والصادر خلال N يوماً."""
        start = days_ago(days)
        if self.db.available:
            try:
                rows = self.db.select(
                    "inventory_movements",
                    columns="product_id,movement_type,quantity,movement_date",
                )
                if not rows:
                    return pd.DataFrame()
                df = pd.DataFrame(rows)
                df["movement_date"] = pd.to_datetime(df["movement_date"])
                df = df[df["movement_date"].dt.date >= start]
                return df
            except Exception as exc:
                logger.warning("تعذّر تحميل الحركات من Supabase (%s) — توليد من المبيعات.", exc)

        # توليد الحركات من بيانات المبيعات التجريبية
        return self._synth_movements_from_sales()

    def _synth_movements_from_sales(self) -> pd.DataFrame:
        """يبني حركات افتراضية (وارد/صادر) من ملف المبيعات التجريبي.

        السيناريو مصمّم لإظهار كل حالات المخزون:
          • p001/p008: حرج (وارد قليل، استهلاك عالٍ)
          • p004/p007: نقص (قريب من نقطة الطلب)
          • p002/p006: صحي
          • p003/p005: راكد (مخزون كبير، استهلاك بطيء)
        """
        sales = load_sample_sales()
        if sales.empty:
            return pd.DataFrame()
        # الصادر = المبيعات
        out_rows = sales.rename(columns={"sale_date": "movement_date"})
        out_rows["movement_type"] = "out"
        out_rows["quantity"] = out_rows["quantity"].astype(float)

        # الوارد: توريدات تاريخية مختلفة لكل منتج لخلق سيناريو واقعي
        products = self.load_products()
        in_rows = []
        # خريطة استراتيجية التوريد لكل منتج
        # (كمية كل دفعة، عدد الدفعات في 90 يوماً، آخر تاريخ توريد قبل كم يوم)
        supply_strategy = {
            "p001": (80, 5, 8),    # صحي
            "p002": (90, 5, 8),    # صحي
            "p003": (120, 6, 50),  # راكد — دفعات كبيرة جداً
            "p004": (50, 5, 12),   # نقص — يكفي تقريباً
            "p005": (30, 4, 70),   # راكد جداً
            "p006": (70, 4, 5),    # صحي
            "p007": (60, 5, 10),   # صحي
            "p008": (60, 3, 5),    # حرج — قريب جداً من النفاد
        }
        for _, p in products.iterrows():
            pid = p["id"]
            qty_per_batch, batches, last_days_ago = supply_strategy.get(
                pid, (int(p["reorder_qty"]), 3, 14)
            )
            for i in range(batches):
                # توزيع الدفعات على الـ 90 يوماً الماضية
                days_ago_supply = last_days_ago + (i * (90 // max(batches, 1)))
                if days_ago_supply > 90:
                    days_ago_supply = 90
                in_rows.append({
                    "product_id": pid,
                    "movement_type": "in",
                    "quantity": float(qty_per_batch),
                    "movement_date": pd.Timestamp(
                        today_local() - timedelta(days=days_ago_supply)
                    ),
                })
        in_df = pd.DataFrame(in_rows)
        # توحيد الأعمدة قبل الدمج
        cols = ["product_id", "movement_type", "quantity", "movement_date"]
        out_clean = out_rows[cols].copy()
        in_clean = in_df[cols].copy()
        return pd.concat([out_clean, in_clean], ignore_index=True)

    # ------------------------------------------------------------------
    # الحسابات الأساسية
    # ------------------------------------------------------------------
    def compute_current_stock(self, movements: pd.DataFrame,
                              product_id: Optional[str] = None) -> pd.Series:
        """يحسب المخزون الحالي لكل منتج = ∑in − ∑out."""
        if movements.empty:
            return pd.Series(dtype=float)
        mv = movements.copy()
        mv["signed_qty"] = np.where(
            mv["movement_type"].isin(["in", "adjustment_in"]),
            mv["quantity"],
            -mv["quantity"],
        )
        if product_id:
            mv = mv[mv["product_id"] == product_id]
        return mv.groupby("product_id")["signed_qty"].sum()

    def compute_daily_consumption(self, movements: pd.DataFrame,
                                  window_days: Optional[int] = None) -> pd.Series:
        """معدل الاستهلاك اليومي = ∑(المبيعات) ÷ عدد الأيام."""
        window_days = window_days or settings.CONSUMPTION_WINDOW_DAYS
        if movements.empty:
            return pd.Series(dtype=float)
        out = movements[movements["movement_type"] == "out"].copy()
        if out.empty:
            return pd.Series(dtype=float)
        out["movement_date"] = pd.to_datetime(out["movement_date"])
        cutoff = pd.Timestamp(today_local() - timedelta(days=window_days))
        out = out[out["movement_date"].dt.date >= cutoff.date()]
        total_qty = out.groupby("product_id")["quantity"].sum()
        return total_qty / window_days

    def compute_days_until_stockout(self, current_stock: pd.Series,
                                    daily_consumption: pd.Series) -> pd.Series:
        """الأيام المتبقية حتى النفاد = المخزون ÷ معدل الاستهلاك اليومي."""
        df = pd.concat([current_stock, daily_consumption], axis=1,
                       keys=["stock", "rate"]).fillna(0)
        days = df.apply(
            lambda r: safe_div(r["stock"], r["rate"], default=None)
            if r["rate"] > 0 else None,
            axis=1,
        )
        return days

    # ------------------------------------------------------------------
    # اللقطة الكاملة
    # ------------------------------------------------------------------
    def snapshot(self) -> List[StockSnapshot]:
        """يبني لقطة كاملة لحالة المخزون لكل المنتجات."""
        products = self.load_products()
        if products.empty:
            logger.warning("لا توجد منتجات في الكتالوج.")
            return []

        movements = self.load_movements(days=max(
            settings.FORECAST_HISTORY_DAYS,
            settings.CONSUMPTION_WINDOW_DAYS,
        ))

        current_stock = self.compute_current_stock(movements)
        consumption = self.compute_daily_consumption(movements)
        days_left = self.compute_days_until_stockout(current_stock, consumption)

        # آخر حركة لكل منتج
        last_mv = (
            movements.sort_values("movement_date")
            .groupby("product_id")["movement_date"]
            .last()
            if not movements.empty else pd.Series(dtype="datetime64[ns]")
        )

        snapshots: List[StockSnapshot] = []
        for _, p in products.iterrows():
            pid = p["id"]
            stock = float(current_stock.get(pid, 0))
            rate = float(consumption.get(pid, 0))
            days = days_left.get(pid)
            days = float(days) if days is not None and not (isinstance(days, float) and np.isnan(days)) else None

            health = classification_health(
                days_left=days,
                current_stock=stock,
                critical_days=settings.CRITICAL_STOCKOUT_DAYS,
                safety_stock=int(p.get("safety_stock", 0)),
                reorder_point=int(p.get("reorder_point", 0)),
            )

            last_date = last_mv.get(pid)
            last_date_str = last_date.isoformat() if last_date is not None and not pd.isna(last_date) else None

            snapshots.append(StockSnapshot(
                product_id=pid,
                sku=str(p.get("sku", "")),
                name=str(p.get("name", "")),
                category=str(p.get("category", "")),
                current_stock=stock,
                daily_consumption_rate=rate,
                days_until_stockout=days,
                reorder_point=int(p.get("reorder_point", 0)),
                reorder_qty=int(p.get("reorder_qty", 0)),
                safety_stock=int(p.get("safety_stock", 0)),
                unit_cost=float(p.get("unit_cost", 0)),
                selling_price=float(p.get("selling_price", 0)),
                stock_health=health,
                last_movement_date=last_date_str,
                supplier_name=str(p.get("supplier_name", "—")),
            ))

        logger.info("تم بناء لقطة المخزون لـ %d منتجاً.", len(snapshots))
        return snapshots

    # ------------------------------------------------------------------
    # تصنيفات سريعة
    # ------------------------------------------------------------------
    def critical_products(self, snapshots: Optional[List[StockSnapshot]] = None
                          ) -> List[StockSnapshot]:
        """المنتجات الحرجة (ستنفد قريباً)."""
        sn = snapshots or self.snapshot()
        return [s for s in sn if s.stock_health in ("critical", "out")]

    def low_stock_products(self, snapshots: Optional[List[StockSnapshot]] = None
                           ) -> List[StockSnapshot]:
        sn = snapshots or self.snapshot()
        return [s for s in sn if s.stock_health == "low"]

    def slow_moving_products(self, snapshots: Optional[List[StockSnapshot]] = None,
                              threshold_days: int = 14) -> List[StockSnapshot]:
        """السلع الراكدة (معدل استهلاك منخفض جداً)."""
        sn = snapshots or self.snapshot()
        return [s for s in sn if s.daily_consumption_rate > 0
                and s.days_until_stockout is not None
                and s.days_until_stockout > 60]

    def overstock_products(self, snapshots: Optional[List[StockSnapshot]] = None
                           ) -> List[StockSnapshot]:
        sn = snapshots or self.snapshot()
        return [s for s in sn if s.stock_health == "overstock"]

    # ------------------------------------------------------------------
    # تحديث قاعدة البيانات
    # ------------------------------------------------------------------
    def persist_stock_status(self, snapshots: List[StockSnapshot]) -> int:
        """يحدّث جدول stock_status في Supabase."""
        if not self.db.available or not snapshots:
            return 0
        rows = [{
            "product_id": s.product_id,
            "current_stock": s.current_stock,
            "daily_consumption_rate": round(s.daily_consumption_rate, 4),
            "days_until_stockout": round(s.days_until_stockout, 2)
                                    if s.days_until_stockout is not None else None,
            "stock_health": s.stock_health,
            "last_movement_date": s.last_movement_date,
            "last_updated": "now()",
        } for s in snapshots]
        try:
            self.db.upsert("stock_status", rows, on_conflict="product_id")
            logger.info("تم تحديث stock_status لـ %d منتجاً.", len(rows))
            return len(rows)
        except Exception as exc:
            logger.error("فشل تحديث stock_status: %s", exc)
            return 0

    # ------------------------------------------------------------------
    # تسجيل حركة جديدة
    # ------------------------------------------------------------------
    def record_movement(self, product_id: str, movement_type: str, quantity: float,
                        unit_cost: Optional[float] = None, reference: Optional[str] = None,
                        notes: Optional[str] = None) -> bool:
        """يسجّل حركة مخزون جديدة (وارد/صادر/تسوية)."""
        if movement_type not in ("in", "out", "adjustment_in", "adjustment_out"):
            logger.error("نوع حركة غير صالح: %s", movement_type)
            return False
        row = {
            "product_id": product_id,
            "movement_type": movement_type,
            "quantity": abs(quantity),
            "unit_cost": unit_cost,
            "reference": reference,
            "notes": notes,
            "movement_date": "now()",
        }
        if not self.db.available:
            logger.info("[وضع محلي] حركة مسجّلة: %s %s %s", product_id, movement_type, quantity)
            return True
        try:
            self.db.insert("inventory_movements", [row])
            logger.info("تم تسجيل حركة: %s — %s — كمية %s",
                        product_id, movement_type, quantity)
            return True
        except Exception as exc:
            logger.error("فشل تسجيل الحركة: %s", exc)
            return False

    def record_sale(self, product_id: str, quantity: float, unit_price: float,
                    sale_date: Optional[date] = None, channel: str = "retail",
                    customer_ref: Optional[str] = None) -> bool:
        """يسجّل عملية بيع جديدة ويُنشئ حركة صادر مقابلة."""
        sale_date = sale_date or today_local()
        row = {
            "product_id": product_id,
            "quantity": abs(quantity),
            "unit_price": unit_price,
            "sale_date": sale_date.isoformat(),
            "channel": channel,
            "customer_ref": customer_ref,
        }
        ok = True
        if self.db.available:
            try:
                self.db.insert("sales", [row])
            except Exception as exc:
                logger.error("فشل تسجيل البيع: %s", exc)
                ok = False
        # حركة صادر مقابلة
        self.record_movement(
            product_id=product_id,
            movement_type="out",
            quantity=quantity,
            reference=f"SALE-{sale_date.isoformat()}",
            notes=f"Sale via {channel}",
        )
        return ok
