"""Аналитика по актам: схемы по дням, итоги, разбивки для круговых диаграмм (чистый Python)."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from . import acts as acts_mod


def _done_day(act: dict) -> date | None:
    """День готовности схемы (done_at — ISO-строка), None — схема не построена."""
    if act.get("status") != "done" or not act.get("done_at"):
        return None
    try:
        return datetime.fromisoformat(act["done_at"]).date()
    except ValueError:
        return None


def _top(counter: Counter, limit: int = 6) -> list[dict]:
    """Самые частые значения; остальные — одной строкой «Другие» (чтобы не плодить цвета)."""
    items = counter.most_common()
    head, tail = items[:limit], items[limit:]
    out = [{"key": k, "value": v} for k, v in head]
    if tail:
        out.append({"key": "__other__", "value": sum(v for _, v in tail)})
    return out


def max_isp(acts: list[dict]) -> dict | None:
    """Акт с наибольшим назначенным номером ИС."""
    with_isp = [a for a in acts if a.get("isp_number") is not None]
    return max(with_isp, key=lambda a: a["isp_number"]) if with_isp else None


def compute(acts: list[dict], today: date | None = None, days: int = 30) -> dict:
    today = today or date.today()
    start = today - timedelta(days=days - 1)

    per_day = {start + timedelta(days=i): {"count": 0, "area": 0.0} for i in range(days)}
    done = [a for a in acts if a.get("status") == "done"]
    for a in done:
        d = _done_day(a)
        if d in per_day:
            per_day[d]["count"] += 1
            per_day[d]["area"] += acts_mod.area(a.get("constructions") or [])["value"]
    daily = [{"date": d.isoformat(), "count": v["count"], "area": round(v["area"], 1)}
             for d, v in per_day.items()]

    week_start = today - timedelta(days=today.weekday())
    done_days = [_done_day(a) for a in done]
    period_count = sum(x["count"] for x in daily)
    best = max(daily, key=lambda x: x["count"]) if daily else None

    kinds: Counter = Counter()
    refineries: Counter = Counter()
    departments: Counter = Counter()
    for a in acts:
        for c in a.get("constructions") or []:
            kinds[c.get("kind") or "auto"] += 1
        refineries[(a.get("refinery") or "").strip() or "—"] += 1
        departments[(a.get("department") or "").strip() or "—"] += 1

    top_isp = max_isp(acts)
    return {
        "days": days,
        "daily": daily,
        "totals": {
            "acts": len(acts),
            "done": len(done),
            "new": sum(1 for a in acts if a.get("status") != "done"),
            "without_isp": sum(1 for a in acts if a.get("isp_number") is None),
            "today": sum(1 for d in done_days if d == today),
            "week": sum(1 for d in done_days if d and week_start <= d <= today),
            "period": period_count,
            "per_day": round(period_count / days, 1) if days else 0,
            "best_day": best if best and best["count"] else None,
            "area_done": round(sum(acts_mod.area(a.get("constructions") or [])["value"] for a in done), 1),
            "constructions": sum(kinds.values()),
        },
        "status": [{"key": "done", "value": len(done)},
                   {"key": "new", "value": len(acts) - len(done)}],
        "kinds": _top(kinds),
        "refineries": _top(refineries),
        "departments": _top(departments),
        "max_isp": top_isp["isp_number"] if top_isp else None,
        "max_isp_act": top_isp["id"] if top_isp else None,
    }
