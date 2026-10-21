"""Тесты актов и схем из нескольких конструкций (без FastAPI)."""
from __future__ import annotations

import os
import tempfile
import unittest


class ActsDb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["TAIS_HOME"] = self.tmp.name

    def tearDown(self):
        os.environ.pop("TAIS_HOME", None)
        self.tmp.cleanup()

    def test_crud_and_isp_numbers(self):
        from tais import db
        a = db.create_act({"number": "AK-717", "date": "24.06.2026", "refinery": "Новойл",
                           "department": "Цех №2", "facility": "36-1-2",
                           "constructions": [{"kind": "tower", "length": 6, "width": 2, "height": 3.2}]})
        b = db.create_act({"number": "AK-718", "date": "24.06.2026", "constructions": []})
        self.assertEqual(a["status"], "new")
        self.assertEqual(a["constructions"][0]["length"], 6)
        done = db.assign_isp_numbers(2180)
        self.assertEqual([x["isp_number"] for x in done], [2180, 2181])
        db.update_act(b["id"], {"status": "done"})
        self.assertEqual([x["number"] for x in db.list_acts("new")], ["AK-717"])
        db.delete_act(a["id"])
        self.assertIsNone(db.get_act(a["id"]))


class TitleFields(unittest.TestCase):
    def test_like_org_v5(self):
        from tais import acts
        conf = {"year": 2026, "isp_prefix": "П1-02",
                "refineries": [{"short": "Новойл", "full": "ПАО АНК \"Башнефть\" \"Башнефть-Новойл\""}]}
        act = {"number": "AK-717", "date": "24.06.2026", "refinery": "Новойл",
               "department": "Цех №2", "facility": "36-1-2", "location": "", "isp_number": 2180}
        f = acts.title_fields(act, conf)
        self.assertEqual(f["[Isp_number]"], "П1-02-Новойл-Ц№2-36-1-2-ИС2180-2026")
        self.assertEqual(f["[Location]"], "Цех №2. 36-1-2. ")
        self.assertEqual(f["[Zavod]"], "ПАО АНК \"Башнефть\" \"Башнефть-Новойл\"")

    def test_abbreviation_and_empty_facility(self):
        from tais import acts
        self.assertEqual(acts.abbreviate("Цех №2"), "Ц№2")
        self.assertEqual(acts.abbreviate("Объект 5"), "О5")
        self.assertEqual(acts.abbreviate("Цех каталитического крекинга"), "ЦКК")
        self.assertEqual(acts.abbreviate("Установка ЭЛОУ-АВТ-6"), "УЭЛОУ-АВТ-6")
        self.assertEqual(acts.abbreviate("Цех по производству серы"), "ЦПС")
        self.assertEqual(acts.abbreviate("36-1-2"), "36-1-2")
        self.assertEqual(acts.abbreviate("Битумная"), "Битумная")
        conf = {"year": 2026, "isp_prefix": "П1-02"}
        act = {"refinery": "УНПЗ", "department": "Газокаталитическое производство",
               "facility": "", "isp_number": 7}
        self.assertEqual(acts.full_isp_number(act, conf), "П1-02-УНПЗ-ГП-ИС7-2026")

    def test_area(self):
        from tais import acts
        one = acts.area([{"length": 2.0, "width": 2.0, "height": 4.2}])
        self.assertEqual(one["text"], "2 х 4.2 = 8.4")
        two = acts.area([{"length": 3, "width": 1, "height": 3.2}, {"length": 1.5, "width": 1, "height": 3.2}])
        self.assertEqual(two["text"], "3 х 3.2 + 1.5 х 3.2 = 9.6 + 4.8 = 14.4")


class MultiScheme(unittest.TestCase):
    def test_two_constructions_one_behind_another(self):
        from tais.generator.scheme import run_scheme
        res = run_scheme([{"kind": "tower", "length": 2, "width": 2, "height": 4.2},
                          {"kind": "auto", "length": 6, "width": 1, "height": 3.2}])
        self.assertEqual(len(res["parts"]), 2)
        self.assertEqual(res["parts"][1]["offset"], 0)
        self.assertEqual(res["parts"][1]["offset_y"], 2000 + 1000)
        self.assertEqual(res["parts"][1]["kind"], "facade")
        # вторая конструкция за первой по Y через 1 м, не пересекаются
        first = max(e["y"] for e in res["elements"] if e["kind"] == "post" and e["y"] < 3000)
        second = min(e["y"] for e in res["elements"] if e["kind"] == "post" and e["y"] >= 3000)
        self.assertEqual(second - first, 1000)
        jacks = sum(r["qty"] for r in res["spec"]["rows"] if r["article"] == "U22011.0500")
        self.assertEqual(jacks, 4 + 6)  # 4 стойки башни + 2×3 фасада 6×1 (2 пролёта по 3 м)


if __name__ == "__main__":
    unittest.main()
