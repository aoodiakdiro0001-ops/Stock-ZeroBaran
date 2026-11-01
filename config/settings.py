"""
=====================================================================
Stock-ZeroBaran — الإعدادات المركزية
المؤلف: Baran Avisat  |  Baranavisat@gmail.com  |  00905313263722
=====================================================================
يقرأ المتغيرات من ملف .env ويوفّرها كإعدادات ممنوعة من التعديل.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# جذر المشروع
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """إعدادات النظام مأخوذة من البيئة."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Supabase ---
    SUPABASE_URL: str = Field(default="")
    SUPABASE_KEY: str = Field(default="")

    # --- AI Engines ---
    GEMINI_API_KEY: str = Field(default="")
    GROQ_API_KEY: str = Field(default="")
    AI_ENGINE: str = Field(default="gemini")  # gemini | groq

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = Field(default="")
    TELEGRAM_CHAT_ID: str = Field(default="")

    # --- عام ---
    TIMEZONE: str = Field(default="Asia/Baghdad")
    CONSUMPTION_WINDOW_DAYS: int = Field(default=30)
    FORECAST_HISTORY_DAYS: int = Field(default=90)
    FORECAST_HORIZON_DAYS: int = Field(default=14)
    CRITICAL_STOCKOUT_DAYS: int = Field(default=5)
    ALERTS_ENABLED: bool = Field(default=True)
    DASHBOARD_ENABLED: bool = Field(default=True)
    LOG_LEVEL: str = Field(default="INFO")

    # --- مسارات داخلية ---
    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"

    @property
    def logs_dir(self) -> Path:
        return PROJECT_ROOT / "logs"

    @property
    def sample_sales_path(self) -> Path:
        return self.data_dir / "sample_sales.csv"

    @property
    def local_db_path(self) -> Path:
        """قاعدة بيانات احتياطية محلية (CSV/JSON) عند عدم توفّر Supabase."""
        return self.data_dir / "local_inventory.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """يُرجع نسخة موحّدة من الإعدادات."""
    return Settings()


def ensure_dirs() -> None:
    """يضمن وجود المجلدات الأساسية."""
    s = get_settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    s.logs_dir.mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "scripts").mkdir(parents=True, exist_ok=True)


# معلومات المشروع للمؤلف
PROJECT_META = {
    "name": "Stock-ZeroBaran",
    "version": "1.0.0",
    "author": "Baran Avisat",
    "email": "Baranavisat@gmail.com",
    "whatsapp": "00905313263722",
    "description": (
        "المنظومة الذاتية الذكية لإدارة المخزون والتنبؤ بالطلب — "
        "نظام متكامل ب resources مجانية 100%"
    ),
}
