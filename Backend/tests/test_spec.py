"""Спецификация: порядок, веса из файла, размещение таблицы."""
from __future__ import annotations

import os
import tempfile
import unittest

from tais.generator import spec
from tests.test_generator import ARCHIVE


class SpecTests(unittest.TestCase):
    def tearDown(self):
        spec.refresh(None)

    def test_total_like_pdf(self):
        # 2.0х1.0х10.2 из архива: итог в PDF-спецификации — 931,16 кг
        counts = ARCHIVE[(2.0, 1.0, 10.2)]
        articles = [a for a, q in counts.items() for _ in range(q)]
        self.assertEqual(spec.build(articles)["total_weight"], 931.16)

    def test_group_order(self):
        arts = ["U07021.2092", "U00281.2000", "S02012.2004", "S11013.2000",
                "S01062.3000", "S01032.0210", "U22011.0500", "U10012.2000", "U00221.2000"]
        order = [r["article"] for r in spec.build(arts)["rows"]]
        self.assertEqual(order, ["U22011.0500", "S01032.0210", "S01062.3000", "S11013.2000",
                                 "S02012.2004", "U00221.2000", "U00281.2000", "U10012.2000",
                                 "U07021.2092"])

    def test_weights_from_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, spec.ELEMENTS_FILE)
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write("Артикул;Наименование в спецификации;Откуда наименование;Вес одного изделия, кг;Ставит генератор\r\n")
                f.write("S11013.3000;S3 Ригель (3.0м);;9,5;да\r\n")
            spec.refresh(d)
            row = spec.build(["S11013.3000"] * 2)["rows"][0]
            self.assertEqual((row["name"], row["unit_weight"], row["total_weight"]),
                             ("S3 Ригель (3.0м)", 9.5, 19.0))


class SpecNames(unittest.TestCase):
    PDF = {
        "S02012.1004": "S2 Диагональ вертикальная (LxH 1.0х2.0м)",
        "S01062.3000": "S2 Стойка с цельноформованным наконечником (3.0м)",
        "S01032.0210": "S2 Элемент стартовый",
        "S11013.2000": "S3 Ригель (2.0м)",
        "U22011.0500": "U1 Домкрат опорный (0.5м)",
        "U07021.2092": "U1 Лестница стальная накидная 75 градусов (7 ступеней)",
        "U00221.2000": "U1 Настил алюминиевый со смещенным люком (2.0х0.75м)",
        "U10012.1000": "U2 Бортик настила стальной (1.0м)",
    }

    def test_rule_matches_pdf(self):
        for art, name in self.PDF.items():
            self.assertEqual(spec.default_spec_name(art), name)

    def test_block_name_column_is_not_used(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, spec.ELEMENTS_FILE), "w", encoding="utf-8-sig") as f:
                f.write("Артикул;Наименование;Вес одного изделия, кг;Ставит генератор\r\n")
                f.write("S11013.3000;Ригель S (3.0м);9,1;да\r\n")
            spec.refresh(d)
            try:
                row = spec.build(["S11013.3000"])["rows"][0]
            finally:
                spec.refresh(None)
            self.assertEqual((row["name"], row["unit_weight"]), ("S3 Ригель (3.0м)", 9.1))


class TableLayout(unittest.TestCase):
    def test_row_height_rule(self):
        from tais.cad.nanocad import SPEC_BOTTOM_MIN, spec_layout
        self.assertEqual(spec_layout(15), (277.7, 8.0))      # как в шаблоне
        self.assertEqual(spec_layout(24), (277.7, 8.0))      # 24 строки — ещё 8 мм
        self.assertEqual(spec_layout(25)[1], 6.0)            # больше 24 — 6 мм
        top, row = spec_layout(36)
        self.assertEqual(row, 6.0)
        self.assertGreaterEqual(top - 36 * row, SPEC_BOTTOM_MIN - 1e-9)


if __name__ == "__main__":
    unittest.main()
