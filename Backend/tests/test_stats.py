"""Тесты аналитики по актам (tais.stats)."""
from __future__ import annotations

import unittest
from datetime import date


def act(i, status="done", done_at=None, isp=None, kind="tower", refinery="Новойл"):
    return {"id": i, "number": f"AK-{i}", "status": status, "done_at": done_at, "isp_number": isp,
            "refinery": refinery, "department": "Цех №2",
            "constructions": [{"kind": kind, "length": 6, "width": 2, "height": 3}]}


class Stats(unittest.TestCase):
    def test_daily_and_totals(self):
        from tais import stats
        today = date(2026, 10, 18)
        acts = [
            act(1, done_at="2026-10-18T10:00:00", isp=2180),
            act(2, done_at="2026-10-18T11:00:00", isp=2185, kind="facade"),
            act(3, done_at="2026-10-01T09:00:00", isp=2181),
            act(4, done_at="2026-08-01T09:00:00", isp=2100),   # вне периода
            act(5, status="new", refinery=""),
        ]
        s = stats.compute(acts, today=today, days=30)
        self.assertEqual(len(s["daily"]), 30)
        self.assertEqual(s["daily"][-1], {"date": "2026-10-18", "count": 2, "area": 36.0})
        self.assertEqual(s["daily"][0]["date"], "2026-09-19")
        t = s["totals"]
        self.assertEqual((t["acts"], t["done"], t["new"], t["today"], t["period"]), (5, 4, 1, 2, 3))
        self.assertEqual(t["week"], 2)            # понедельник 12.10 — воскресенье 18.10
        self.assertEqual(t["best_day"]["date"], "2026-10-18")
        self.assertEqual(s["max_isp"], 2185)
        self.assertEqual(s["max_isp_act"], 2)
        self.assertEqual({k["key"]: k["value"] for k in s["kinds"]}, {"tower": 4, "facade": 1})
        self.assertIn({"key": "—", "value": 1}, s["refineries"])

    def test_other_bucket_and_empty(self):
        from tais import stats
        acts = [act(i, refinery=f"Завод {i}") for i in range(9)]
        s = stats.compute(acts, today=date(2026, 10, 18))
        self.assertEqual(len(s["refineries"]), 7)
        self.assertEqual(s["refineries"][-1], {"key": "__other__", "value": 3})
        empty = stats.compute([], today=date(2026, 10, 18))
        self.assertIsNone(empty["max_isp"])
        self.assertIsNone(empty["totals"]["best_day"])


if __name__ == "__main__":
    unittest.main()
