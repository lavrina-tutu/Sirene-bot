"""Telegram-уведомления (HTTP, без сторонних SDK).

ТЗ §7: TG-алерты шлёт ТОЛЬКО ручной запуск. Cron/test — молча.
Эта обвязка просто отправляет сообщение; решение «слать или нет» — в __main__.
"""
from __future__ import annotations

import json
from typing import Optional

import requests
from loguru import logger


def send_message(
    bot_token: Optional[str],
    chat_id: Optional[str],
    text: str,
    parse_mode: str = "HTML",
    disable_notification: bool = False,
    timeout: float = 15.0,
) -> bool:
    """Отправить сообщение в Telegram. True — успех, False — отказ/ошибка.

    Если bot_token / chat_id отсутствуют — тихий no-op.
    """
    if not bot_token or not chat_id:
        logger.warning("TG skipped: bot_token/chat_id missing")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:4000],
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
        "disable_notification": disable_notification,
    }
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        if r.status_code != 200:
            logger.warning(f"TG send failed: {r.status_code} {r.text[:200]}")
            return False
        body = r.json()
        return bool(body.get("ok"))
    except requests.RequestException as exc:
        logger.warning(f"TG network error: {exc}")
        return False
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning(f"TG bad response: {exc}")
        return False
