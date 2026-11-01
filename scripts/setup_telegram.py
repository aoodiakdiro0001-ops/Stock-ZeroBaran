#!/usr/bin/env python3
"""
=====================================================================
Stock-ZeroBaran — فحص إعداد تليجرام
المؤلف: Baran Avisat  |  Baranavisat@gmail.com  |  00905313263722
=====================================================================
يتحقّق من صحة إعدادات Telegram Bot ويُرسل رسالة اختبار.

التشغيل:
  python scripts/setup_telegram.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import get_settings
from src.utils.helpers import setup_logging, print_banner

logger = setup_logging("INFO")


def main() -> int:
    print_banner()
    settings = get_settings()
    print("🔧 فحص إعدادات Telegram...\n")

    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    issues = []
    if not token or "your-" in token:
        issues.append("❌ TELEGRAM_BOT_TOKEN غير مُهيّأ.")
    if not chat_id or "your-" in chat_id:
        issues.append("❌ TELEGRAM_CHAT_ID غير مُهيّأ.")

    if issues:
        print("\n".join(issues))
        print("\n📋 الخطوات:")
        print("  1) تحدّث إلى @BotFather في تليجرام")
        print("  2) أرسل /newbot وأنشئ بوتاً جديداً")
        print("  3) انسخ التوكن وضعه في ملف .env")
        print("  4) تحدّث إلى بوتك الجديد وأرسل /start")
        print("  5) تحدّث إلى @userinfobot للحصول على chat_id")
        print("  6) ضع chat_id في ملف .env")
        return 1

    print(f"✅ التوكن: {token[:10]}...{token[-4:]}")
    print(f"✅ chat_id: {chat_id}")

    # إرسال رسالة اختبار
    print("\n📨 إرسال رسالة اختبار...")
    import requests
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": (
            "✅ <b>تم ربط Stock-ZeroBaran بنجاح!</b>\n\n"
            "ستصلك تنبيهات المخزون هنا تلقائياً.\n\n"
            "📦 <i>Stock-ZeroBaran</i>\n"
            "المؤلف: Baran Avisat"
        ),
        "parse_mode": "HTML",
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            print("✅ تم إرسال رسالة الاختبار بنجاح! تحقّق من تليجرام.")
            return 0
        print(f"❌ فشل الإرسال {r.status_code}: {r.text}")
        return 2
    except Exception as exc:
        print(f"❌ استثناء: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
