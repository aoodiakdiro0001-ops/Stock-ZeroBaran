"""
=====================================================================
Stock-ZeroBaran — لوحة التحكم المرئية (Streamlit Dashboard)
المؤلف: Baran Avisat  |  Baranavisat@gmail.com  |  00905313263722
=====================================================================
تشغيل:
  streamlit run src/dashboard/app.py

توفر:
  • نظرة عامة على المخزون ومؤشرات الأداء الرئيسية
  • جدول المخزون مع فلاتر حسب الحالة والتصنيف
  • تفاصيل المنتج ورسم بياني لحركة الاستهلاك
  • التنبؤات الذكية ومقترحات إعادة الطلب
  • سجل التنبيهات
"""
from __future__ import annotations

import sys
from pathlib import Path

# ضمان وصول الاستيراد إلى جذر المشروع
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.settings import PROJECT_META, get_settings
from src.core.alerts import AlertEngine, format_stockout_alert
from src.core.forecasting import ForecastingEngine, get_forecast_engine
from src.core.inventory import InventoryEngine
from src.utils.helpers import fmt_money, fmt_qty, setup_logging

setup_logging("INFO")
settings = get_settings()


# ===================================================================
# إعداد الصفحة
# ===================================================================
st.set_page_config(
    page_title="Stock-ZeroBaran — لوحة المخزون الذكية",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS مخصّص
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #0ea5e9 100%);
        padding: 1.2rem 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .main-header h1 { margin: 0; font-weight: 700; }
    .main-header .sub { opacity: 0.85; font-size: 0.9rem; margin-top: 0.3rem; }
    .metric-card {
        background: white;
        padding: 1.2rem;
        border-radius: 10px;
        border-right: 4px solid;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .footer-bar {
        text-align: center; opacity: 0.7; font-size: 0.85rem;
        margin-top: 2rem; padding: 1rem; border-top: 1px solid #ddd;
    }
    .health-critical { color: #dc2626; font-weight: 700; }
    .health-low { color: #d97706; font-weight: 700; }
    .health-healthy { color: #16a34a; font-weight: 700; }
    .health-out { color: #1f2937; font-weight: 700; }
    .health-overstock { color: #2563eb; font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# ===================================================================
# الترويسة
# ===================================================================
st.markdown(f"""
<div class="main-header">
    <h1>📦 Stock-ZeroBaran</h1>
    <div class="sub">المنظومة الذاتية الذكية لإدارة المخزون والتنبؤ بالطلب — المؤلف: Baran Avisat</div>
</div>
""", unsafe_allow_html=True)


# ===================================================================
# التخزين المؤقت للجلسة
# ===================================================================
@st.cache_data(ttl=300, show_spinner=False)
def build_snapshot() -> pd.DataFrame:
    engine = InventoryEngine()
    snaps = engine.snapshot()
    if not snaps:
        return pd.DataFrame()
    df = pd.DataFrame([s.to_dict() for s in snaps])
    return df


@st.cache_data(ttl=300, show_spinner=False)
def build_forecasts(snapshots_dict: list) -> pd.DataFrame:
    """يبني التنبؤات لكل المنتجات."""
    from src.core.inventory import StockSnapshot
    snapshots = [StockSnapshot(**d) for d in snapshots_dict]
    fc_engine = get_forecast_engine()
    forecasts = fc_engine.forecast_all(snapshots)
    if not forecasts:
        return pd.DataFrame()
    return pd.DataFrame([f.to_dict() for f in forecasts])


# ===================================================================
# الشريط الجانبي
# ===================================================================
with st.sidebar:
    st.markdown("### ⚙️ التحكم")
    st.markdown(f"**الإصدار:** {PROJECT_META['version']}")
    st.markdown(f"**المؤلف:** {PROJECT_META['author']}")
    st.markdown("---")

    auto_refresh = st.checkbox("تحديث تلقائي كل 5 دقائق", value=False)
    run_check = st.button("🔄 تشغيل فحص فوري", use_container_width=True)
    show_forecasts = st.checkbox("عرض التنبؤات الذكية", value=True)

    st.markdown("---")
    st.markdown("### 📞 الدعم")
    st.markdown(f"✉️ {PROJECT_META['email']}")
    st.markdown(f"💬 {PROJECT_META['whatsapp']}")

    st.markdown("---")
    st.caption("© 2026 Baran Avisat — جميع الحقوق محفوظة")


if auto_refresh:
    st_autorefresh_placeholder = st.empty()
    import time
    # تحديث بسيط بطلب إعادة تشغيل
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = time.time()
    elif time.time() - st.session_state.last_refresh > 300:
        st.session_state.last_refresh = time.time()
        build_snapshot.clear()


# ===================================================================
# تشغيل فحص فوري
# ===================================================================
if run_check:
    with st.spinner("جاري تشغيل الفحص الكامل..."):
        import subprocess
        result = subprocess.run(
            ["python", str(ROOT / "scripts" / "run_inventory_check.py")],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        if result.returncode == 0:
            st.success("✅ تم تشغيل الفحص بنجاح!")
            build_snapshot.clear()
        else:
            st.error(f"فشل الفحص: {result.stderr[:500]}")
        st.code(result.stdout[-2000:])


# ===================================================================
# تحميل البيانات
# ===================================================================
with st.spinner("جاري تحميل حالة المخزون..."):
    snap_df = build_snapshot()

if snap_df.empty:
    st.warning("⚠️ لا توجد بيانات مخزون. شغّل `scripts/seed_sample_data.py` أولاً لتعبئة بيانات تجريبية.")
    st.code("python scripts/seed_sample_data.py", language="bash")
    st.stop()

forecasts_df = pd.DataFrame()
if show_forecasts:
    with st.spinner("جاري بناء التنبؤات الذكية..."):
        try:
            forecasts_df = build_forecasts(snap_df.to_dict("records"))
        except Exception as exc:
            st.info(f"التنبؤات غير متاحة حالياً: {exc}")


# ===================================================================
# مؤشرات الأداء الرئيسية (KPIs)
# ===================================================================
total_products = len(snap_df)
critical_count = len(snap_df[snap_df["stock_health"].isin(["critical", "out"])])
low_count = len(snap_df[snap_df["stock_health"] == "low"])
healthy_count = len(snap_df[snap_df["stock_health"] == "healthy"])
overstock_count = len(snap_df[snap_df["stock_health"] == "overstock"])
inventory_value = (snap_df["current_stock"] * snap_df["unit_cost"]).sum()
potential_revenue = (snap_df["current_stock"] * snap_df["selling_price"]).sum()

col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    st.metric("📦 إجمالي المنتجات", total_products)
with col2:
    st.metric("🟢 سليم", healthy_count)
with col3:
    st.metric("🟡 نقص", low_count)
with col4:
    st.metric("🔴 حرج", critical_count, delta=f"-{critical_count}" if critical_count else None,
              delta_color="inverse")
with col5:
    st.metric("💰 قيمة المخزون", fmt_money(inventory_value))
with col6:
    st.metric("💵 إيراد محتمل", fmt_money(potential_revenue))


# ===================================================================
# تبويبات الصفحة
# ===================================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 نظرة عامة",
    "📦 جدول المخزون",
    "🤖 التنبؤات الذكية",
    "🚨 التنبيهات",
])


# --- تبويب 1: نظرة عامة ---
with tab1:
    st.markdown("### 📊 توزيع صحة المخزون")
    health_counts = snap_df["stock_health"].value_counts().reset_index()
    health_counts.columns = ["الحالة", "العدد"]
    color_map = {
        "healthy": "#16a34a", "low": "#d97706", "critical": "#dc2626",
        "out": "#1f2937", "overstock": "#2563eb", "unknown": "#9ca3af",
    }
    fig_health = px.bar(
        health_counts, x="الحالة", y="العدد", color="الحالة",
        color_discrete_map=color_map,
        title="توزيع المنتجات حسب صحة المخزون",
    )
    fig_health.update_layout(showlegend=False, height=350)
    st.plotly_chart(fig_health, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### 💰 قيمة المخزون حسب التصنيف")
        by_cat = snap_df.groupby("category").apply(
            lambda g: (g["current_stock"] * g["unit_cost"]).sum()
        ).reset_index()
        by_cat.columns = ["التصنيف", "القيمة"]
        fig_cat = px.pie(by_cat, values="القيمة", names="التصنيف",
                          hole=0.4, title="توزيع القيمة")
        st.plotly_chart(fig_cat, use_container_width=True)
    with col_b:
        st.markdown("### ⏳ الأيام المتبقية حتى النفاد")
        plot_df = snap_df.dropna(subset=["days_until_stockout"]).copy()
        if not plot_df.empty:
            fig_days = px.bar(
                plot_df.sort_values("days_until_stockout"),
                x="name", y="days_until_stockout",
                color="stock_health", color_discrete_map=color_map,
                title="أيام النفاد المتوقّعة لكل منتج",
            )
            fig_days.update_layout(height=350, xaxis_tickangle=-30)
            st.plotly_chart(fig_days, use_container_width=True)
        else:
            st.info("لا توجد بيانات كافية.")


# --- تبويب 2: جدول المخزون ---
with tab2:
    st.markdown("### 📦 جدول المخزون التفصيلي")
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        health_filter = st.multiselect(
            "فلترة حسب الحالة",
            options=["healthy", "low", "critical", "out", "overstock"],
            default=[],
        )
    with col_f2:
        categories = snap_df["category"].unique().tolist()
        cat_filter = st.multiselect("فلترة حسب التصنيف", options=categories, default=[])
    with col_f3:
        search = st.text_input("🔍 بحث بالاسم أو SKU")

    view = snap_df.copy()
    if health_filter:
        view = view[view["stock_health"].isin(health_filter)]
    if cat_filter:
        view = view[view["category"].isin(cat_filter)]
    if search:
        mask = view["name"].str.contains(search, case=False, na=False) | \
               view["sku"].str.contains(search, case=False, na=False)
        view = view[mask]

    display_cols = [
        "sku", "name", "category", "current_stock", "daily_consumption_rate",
        "days_until_stockout", "reorder_point", "reorder_qty", "stock_health",
        "unit_cost", "selling_price", "supplier_name",
    ]
    rename_map = {
        "sku": "SKU", "name": "المنتج", "category": "التصنيف",
        "current_stock": "المتبقي", "daily_consumption_rate": "معدل الاستهلاك/يوم",
        "days_until_stockout": "أيام حتى النفاد", "reorder_point": "نقطة الطلب",
        "reorder_qty": "كمية الطلب", "stock_health": "الحالة",
        "unit_cost": "التكلفة", "selling_price": "سعر البيع", "supplier_name": "المورّد",
    }
    st.dataframe(
        view[display_cols].rename(columns=rename_map),
        use_container_width=True,
        hide_index=True,
        height=500,
    )

    # تفاصيل منتج
    st.markdown("---")
    st.markdown("### 🔍 تفاصيل منتج")
    selected_sku = st.selectbox("اختر منتجاً", view["sku"].tolist() if not view.empty else [])
    if selected_sku:
        row = snap_df[snap_df["sku"] == selected_sku].iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("المتبقي", fmt_qty(row["current_stock"]))
        c2.metric("معدل الاستهلاك/يوم", f"{row['daily_consumption_rate']:.2f}")
        c3.metric("أيام حتى النفاد",
                  f"{row['days_until_stockout']:.0f}" if pd.notna(row["days_until_stockout"]) else "—")
        c4.metric("قيمة المخزون", fmt_money(row["current_stock"] * row["unit_cost"]))


# --- تبويب 3: التنبؤات ---
with tab3:
    if forecasts_df.empty:
        st.info("الت forecasts غير متاحة. فعّل GEMINI_API_KEY أو GROQ_API_KEY في ملف .env")
    else:
        st.markdown("### 🤖 التنبؤات الذكية ومقترحات إعادة الطلب")
        fc_view = forecasts_df.rename(columns={
            "sku": "SKU", "name": "المنتج",
            "expected_demand": "الطلب المتوقع",
            "confidence": "الثقة %",
            "suggested_reorder": "كمية الطلب المقترحة",
            "days_until_stockout": "أيام النفاد",
            "model_used": "المحرك",
            "reasoning": "التفسير",
            "seasonal_note": "موسمي",
        })
        st.dataframe(
            fc_view[["SKU", "المنتج", "الطلب المتوقع", "الثقة %",
                      "كمية الطلب المقترحة", "أيام النفاد", "المحرك", "موسمي", "التفسير"]],
            use_container_width=True,
            hide_index=True,
            height=500,
        )
        st.markdown("---")
        st.markdown("### 📈 الطلب المتوقع مقابل المخزون الحالي")
        merged = forecasts_df.merge(
            snap_df[["product_id", "current_stock"]], on="product_id"
        )
        fig_fc = go.Figure()
        fig_fc.add_trace(go.Bar(
            x=merged["name"], y=merged["current_stock"],
            name="المخزون الحالي", marker_color="#0ea5e9",
        ))
        fig_fc.add_trace(go.Bar(
            x=merged["name"], y=merged["expected_demand"],
            name="الطلب المتوقع", marker_color="#f59e0b",
        ))
        fig_fc.add_trace(go.Bar(
            x=merged["name"], y=merged["suggested_reorder"],
            name="كمية الطلب المقترحة", marker_color="#16a34a",
        ))
        fig_fc.update_layout(barmode="group", height=400,
                              xaxis_tickangle=-30, title="مقارنة الطلب والعرض")
        st.plotly_chart(fig_fc, use_container_width=True)


# --- تبويب 4: التنبيهات ---
with tab4:
    st.markdown("### 🚨 التنبيهات النشطة")
    critical_snaps = snap_df[snap_df["stock_health"].isin(["critical", "out"])]
    if critical_snaps.empty:
        st.success("✅ لا توجد تنبيهات حرجة حالياً.")
    else:
        from src.core.inventory import StockSnapshot
        for _, row in critical_snaps.iterrows():
            snap = StockSnapshot(**row.to_dict())
            fc = None
            if not forecasts_df.empty:
                fc_rows = forecasts_df[forecasts_df["product_id"] == snap.product_id]
                if not fc_rows.empty:
                    from src.core.forecasting import DemandForecast
                    fc = DemandForecast(**fc_rows.iloc[0].to_dict())
            st.warning(format_stockout_alert(snap, fc))

    # تنبيه سلع راكدة
    slow = snap_df[snap_df["stock_health"] == "overstock"]
    if not slow.empty:
        st.markdown("### 🔵 السلع الراكدة")
        for _, row in slow.iterrows():
            st.info(f"📦 {row['name']} ({row['sku']}) — المخزون: {fmt_qty(row['current_stock'])} "
                    f"وحدة، معدل الاستهلاك اليومي: {row['daily_consumption_rate']:.2f}")


# ===================================================================
# التذييل
# ===================================================================
st.markdown("""
<div class="footer-bar">
    Stock-ZeroBaran v{ver} — المنظومة الذاتية الذكية لإدارة المخزون والتنبؤ بالطلب<br>
    المؤلف: Baran Avisat  |  ✉️ Baranavisat@gmail.com  |  💬 00905313263722<br>
    © 2026 جميع الحقوق محفوظة — رخصة MIT
</div>
""".format(ver=PROJECT_META["version"]), unsafe_allow_html=True)
