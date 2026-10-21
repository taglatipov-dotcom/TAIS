"""Масштаб видов листа A3 и размеры на листе (без nanoCAD)."""
from __future__ import annotations

import unittest

from tais.cad import views as V
from tais.generator.scheme import run_scheme

ORIGIN = (1754.0, 1277.0, 0.0)


def sheet(*items):
    res = run_scheme([{"length": l, "width": w, "height": h} for l, w, h in items])
    return V.plan_sheet(V.TEMPLATE_A3, res["elements"], res["parts"], ORIGIN), res


class Projection(unittest.TestCase):
    def test_classify_template(self):
        s = V.classify(V.TEMPLATE_A3)
        self.assertEqual({n: x.index for n, x in s.items()},
                         {"iso": 0, "front": 1, "side": 2, "plan": 3, "picture": 4})

    def test_matches_manual_scheme(self):
        """Схема 2.0х1.0х10.2 из архива: экраны и размеры сделаны вручную."""
        s = V.classify(V.TEMPLATE_A3)
        cases = [
            ("front", (2336.478, 696.97, 2828.99), (1603, 3380),
             [((3038, 2171, 0), (167.6, 148.1)), ((5038, 2171, 0), (183.9, 148.1))]),
            ("side", (3301.93, 2563.08, 3001.53), (-183, 2960),
             [((4000, 2171, 0), (278.3, 150.1)), ((4000, 3171, 605), (286.4, 155.0)),
              ((4000, 3171, 10105), (286.4, 232.3))]),
        ]
        for name, target, ctr, pts in cases:
            slot = s[name]
            t = slot.project(target)
            view = V.View(slot, 16646 / slot.height, (t[0] + ctr[0], t[1] + ctr[1]))
            for p, expected in pts:
                got = view.to_paper(p)
                self.assertAlmostEqual(got[0], expected[0], delta=0.15)
                self.assertAlmostEqual(got[1], expected[1], delta=0.15)

    def test_center_wcs_maps_to_slot_center(self):
        sh, _ = sheet((6, 1, 4.2))
        for v in sh["views"].values():
            px, py = v.to_paper(v.center_wcs)
            self.assertAlmostEqual(px, v.slot.center[0], places=6)
            self.assertAlmostEqual(py, v.slot.center[1], places=6)


class Scales(unittest.TestCase):
    def assert_inside(self, sh):
        lo, hi = sh["box"]
        for name, v in sh["views"].items():
            x0, y0, x1, y1 = V._usable(v.slot)
            for c in V._corners(lo, hi):
                x, y = v.to_paper(c)
                self.assertTrue(x0 - 1e-6 <= x <= x1 + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6,
                                f"{name}: точка {c} вне экрана ({x:.1f}, {y:.1f})")

    def test_fits_and_standard(self):
        for items in [((21, 1, 4.7),), ((2, 1, 10.2),), ((1.5, 1, 2),), ((12, 3, 4.2),),
                      ((11, 3, 30.2), (11, 3, 30.2), (11, 3, 15.2))]:
            sh, _ = sheet(*items)
            self.assert_inside(sh)
            for v in sh["views"].values():
                self.assertIn(v.scale, V.SCALES)

    def test_front_and_plan_share_scale(self):
        sh, _ = sheet((21, 1, 4.7))
        self.assertEqual(sh["views"]["front"].scale, sh["views"]["plan"].scale)
        self.assertEqual(sh["views"]["front"].scale, 250)

    def test_side_own_scale_for_long_facade(self):
        sh, _ = sheet((21, 1, 4.7))
        self.assertLess(sh["views"]["side"].scale, sh["views"]["front"].scale)

    def test_tower_side_same_scale_ground_aligned(self):
        sh, _ = sheet((2, 1, 10.2))
        f, s = sh["views"]["front"], sh["views"]["side"]
        self.assertEqual(f.scale, s.scale)
        self.assertAlmostEqual(f.to_paper(ORIGIN)[1], s.to_paper(ORIGIN)[1], places=6)

    def test_small_tower_not_larger_than_1_50(self):
        sh, _ = sheet((1.5, 1, 2))
        self.assertTrue(all(v.scale >= 50 for v in sh["views"].values()))


class Dims(unittest.TestCase):
    def test_labels_like_manual(self):
        sh, _ = sheet((2, 1, 10.2))
        texts = [d.text for d in sh["dims"]]
        self.assertEqual(texts[:2], ["2000", "1000"])
        self.assertEqual(texts[2:], ["0", "700", "2700", "4700", "6700", "8700", "10200"])

    def test_length_dim_under_front(self):
        sh, res = sheet((21, 1, 4.7))
        d = sh["dims"][0]
        f = sh["views"]["front"]
        ground = f.to_paper(ORIGIN)[1]
        self.assertEqual(d.text, "21000")
        self.assertAlmostEqual(d.line[1], ground - V.DIM_OFFSET, places=2)
        self.assertAlmostEqual(d.p2[0] - d.p1[0], 21000 / f.scale, places=2)

    def test_chain_inside_side_slot(self):
        for items in [((2, 1, 10.2),), ((11, 3, 30.2), (11, 3, 15.2))]:
            sh, _ = sheet(*items)
            s = sh["views"]["side"].slot
            right = s.center[0] + s.width / 2
            for d in sh["dims"]:
                if d.kind == "ordinate":
                    self.assertLess(d.line[0] + 10, right)   # подпись ~10 мм за концом выноски

    def test_text_spread(self):
        self.assertEqual(V._spread([0, 1, 10, 11], 3), [0, 3, 10, 13])

    def test_several_constructions(self):
        """Друг за другом по Y: длины на виде спереди в разных рядах, ширины сбоку — в одном,
        отметки — одной общей цепочкой."""
        sh, res = sheet((6, 1, 4.2), (3, 1, 2.2))
        self.assertEqual([p["offset_y"] for p in res["parts"]], [0, 2000])
        front = [d for d in sh["dims"] if d.view == "front"]
        self.assertEqual([d.text for d in front], ["6000", "3000"])
        self.assertAlmostEqual(front[0].line[1] - front[1].line[1], V.DIM_ROW_STEP, places=3)
        widths = [d for d in sh["dims"] if d.view == "side" and d.kind == "rotated"]
        self.assertEqual([d.text for d in widths], ["1000", "1000"])
        self.assertEqual(len({d.line[1] for d in widths}), 1)
        chain = [d.text for d in sh["dims"] if d.kind == "ordinate"]
        self.assertEqual(chain, ["0", "700", "2200", "2700", "4200"])
        self.assertEqual(len({d.line[0] for d in sh["dims"] if d.kind == "ordinate"}), 1)

    def test_same_length_once(self):
        sh, _ = sheet((6, 1, 4.2), (6, 1, 4.2))
        self.assertEqual([d.text for d in sh["dims"] if d.view == "front"], ["6000"])

if __name__ == "__main__":
    unittest.main()
