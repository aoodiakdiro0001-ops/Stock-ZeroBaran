"""
=====================================================================
Stock-ZeroBaran — عميل Supabase
الطبقة: Persistence Layer
المؤلف: Baran Avisat  |  Baranavisat@gmail.com  |  00905313263722
=====================================================================
يوفّر نقطة اتصال موحّدة بقاعدة بيانات Supabase PostgreSQL
مع إعادة المحاولة (retry) والتسجيل (logging).
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config.settings import get_settings

logger = logging.getLogger("stockzerobaran.database")

settings = get_settings()


class DatabaseError(Exception):
    """خطأ في الاتصال بقاعدة البيانات أو تنفيذ الاستعلام."""


class SupabaseClient:
    """عميل Supabase موحّد مع إعادة المحاولة والتسجيل."""

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None) -> None:
        self.url = url or settings.SUPABASE_URL
        self.key = key or settings.SUPABASE_KEY
        if not self.url or not self.key or "your-" in str(self.url):
            logger.warning(
                "Supabase credentials غير مُهيّأة. سيُستخدم وضع البيانات المحلية (CSV)."
            )
            self._client = None
            self._available = False
        else:
            try:
                from supabase import create_client, Client
                self._client: Optional[Client] = create_client(self.url, self.key)
                self._available = True
                logger.info("✅ تم الاتصال بـ Supabase بنجاح.")
            except Exception as exc:
                logger.error("فشل الاتصال بـ Supabase: %s", exc)
                self._client = None
                self._available = False

    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        return self._available

    # ------------------------------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(DatabaseError),
        reraise=True,
    )
    def select(self, table: str, columns: str = "*", filters: Optional[Dict[str, Any]] = None,
               limit: Optional[int] = None, order_by: Optional[str] = None) -> List[Dict[str, Any]]:
        """SELECT من جدول مع دعم الفلاتر والترتيب."""
        if not self._available:
            raise DatabaseError("Supabase غير متاح.")
        try:
            query = self._client.table(table).select(columns)
            if filters:
                for column, value in filters.items():
                    query = query.eq(column, value)
            if order_by:
                col, _, direction = order_by.partition(":")
                query = query.order(col, desc=(direction.lower() == "desc"))
            if limit:
                query = query.limit(limit)
            response = query.execute()
            return response.data or []
        except Exception as exc:
            logger.error("فشل SELECT من %s: %s", table, exc)
            raise DatabaseError(str(exc)) from exc

    # ------------------------------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(DatabaseError),
        reraise=True,
    )
    def insert(self, table: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """INSERT صفوف متعدّدة في جدول."""
        if not self._available:
            raise DatabaseError("Supabase غير متاح.")
        try:
            response = self._client.table(table).insert(rows).execute()
            return response.data or []
        except Exception as exc:
            logger.error("فشل INSERT في %s: %s", table, exc)
            raise DatabaseError(str(exc)) from exc

    # ------------------------------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(DatabaseError),
        reraise=True,
    )
    def upsert(self, table: str, rows: List[Dict[str, Any]],
               on_conflict: str = "id") -> List[Dict[str, Any]]:
        """UPSERT صفوف في جدول."""
        if not self._available:
            raise DatabaseError("Supabase غير متاح.")
        try:
            response = (
                self._client.table(table)
                .upsert(rows, on_conflict=on_conflict)
                .execute()
            )
            return response.data or []
        except Exception as exc:
            logger.error("فشل UPSERT في %s: %s", table, exc)
            raise DatabaseError(str(exc)) from exc

    # ------------------------------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(DatabaseError),
        reraise=True,
    )
    def update(self, table: str, filters: Dict[str, Any],
               values: Dict[str, Any]) -> List[Dict[str, Any]]:
        """UPDATE صفوف في جدول وفق فلاتر."""
        if not self._available:
            raise DatabaseError("Supabase غير متاح.")
        try:
            query = self._client.table(table).update(values)
            for column, value in filters.items():
                query = query.eq(column, value)
            response = query.execute()
            return response.data or []
        except Exception as exc:
            logger.error("فشل UPDATE في %s: %s", table, exc)
            raise DatabaseError(str(exc)) from exc

    # ------------------------------------------------------------------
    def raw_sql(self, sql: str) -> Any:
        """تنفيذ استعلام SQL خام عبر دالة RPC."""
        if not self._available:
            raise DatabaseError("Supabase غير متاح.")
        try:
            return self._client.rpc("exec_sql", {"query": sql}).execute()
        except Exception as exc:
            logger.error("فشل تنفيذ SQL خام: %s", exc)
            raise DatabaseError(str(exc)) from exc


# ===================================================================
# نقطة وصول موحّدة (Singleton)
# ===================================================================
@lru_cache(maxsize=1)
def get_db() -> SupabaseClient:
    """يُرجع نسخة موحّدة من عميل Supabase."""
    return SupabaseClient()
