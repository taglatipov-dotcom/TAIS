"""Демо-версия: программа работает до даты, вшитой при сборке.

build.ps1 -DemoUntil 2026-11-15 записывает дату в tais/_build_info.py (DEMO_UNTIL),
без параметра — полная версия (DEMO_UNTIL = None).

Защита от перевода часов назад: программа запоминает самое позднее время запуска
(в %APPDATA%\\TAIS\\.state и в реестре HKCU\\Software\\TAIS) и блокируется, если часы
на компьютере отстают от него больше чем на сутки.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from datetime import date, datetime, timedelta

from .settings import app_dir

try:
    from ._build_info import DEMO_UNTIL
except ImportError:          # разработка: файла нет — полная версия
    DEMO_UNTIL = None

_SALT = "tais-demo-7f3c"
_REG_KEY = r"Software\TAIS"
_REG_NAME = "Seen"
_TOLERANCE = timedelta(days=1)   # смена часового пояса, мелкие поправки часов


def _sign(ts: str) -> str:
    return hashlib.sha256(f"{_SALT}|{ts}".encode()).hexdigest()[:16]


def _pack(dt: datetime) -> str:
    ts = dt.isoformat(timespec="seconds")
    return base64.b64encode(json.dumps({"t": ts, "s": _sign(ts)}).encode()).decode()


def _unpack(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        d = json.loads(base64.b64decode(raw))
        if d.get("s") != _sign(d["t"]):
            return None
        return datetime.fromisoformat(d["t"])
    except (ValueError, KeyError, TypeError):
        return None


def _read_reg() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY) as k:
            return winreg.QueryValueEx(k, _REG_NAME)[0]
    except OSError:
        return None


def _write_reg(value: str) -> None:
    if sys.platform != "win32":
        return
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_KEY) as k:
            winreg.SetValueEx(k, _REG_NAME, 0, winreg.REG_SZ, value)
    except OSError:
        pass


def _state_file():
    return app_dir() / ".state"


def _last_seen() -> datetime | None:
    try:
        file_raw = _state_file().read_text(encoding="utf-8").strip()
    except OSError:
        file_raw = None
    seen = [d for d in (_unpack(file_raw), _unpack(_read_reg())) if d]
    return max(seen) if seen else None


def _remember(now: datetime) -> None:
    raw = _pack(now)
    try:
        _state_file().write_text(raw, encoding="utf-8")
    except OSError:
        pass
    _write_reg(raw)


def until() -> date | None:
    return date.fromisoformat(DEMO_UNTIL) if DEMO_UNTIL else None


def status() -> dict:
    """{demo, until, days_left, expired, reason} — для шапки и блокировки API."""
    end = until()
    if end is None:
        return {"demo": False, "until": None, "days_left": None, "expired": False, "reason": None}
    now = datetime.now()
    last = _last_seen()
    reason = None
    if last and now < last - _TOLERANCE:
        reason = "clock"
    elif now.date() > end:
        reason = "expired"
    if last is None or now - last > timedelta(minutes=10):   # не пишем на каждый запрос
        _remember(now)
    return {
        "demo": True,
        "until": end.strftime("%d.%m.%Y"),
        "days_left": max((end - now.date()).days + 1, 0),
        "expired": reason is not None,
        "reason": reason,
    }
