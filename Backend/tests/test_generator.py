"""Тесты генератора. Запуск из папки Backend:  python -m unittest -v"""
from __future__ import annotations

import unittest
from collections import Counter

from tais.generator import ConstructionInput, SplitError, run, classify
from tais.generator.bays import split_length
from tais.generator.model import BASE_LEVEL, Cell, Structure
from tais.generator.rules import generate

# Количество элементов в ваших чертежах из архива ORG_V5 (прочитано из DWG).
ARCHIVE = {
    (2.0, 2.0, 4.2): {"S01022.1000": 4, "S01032.0210": 4, "S01062.3000": 4, "S02012.2004": 3,
                      "S11013.2000": 32, "U00221.2000": 1, "U00281.2000": 9, "U07021.2092": 1,
                      "U10012.2000": 4, "U22011.0500": 4},
    (2.0, 1.0, 10.2): {"S01032.0210": 4, "S01062.1000": 4, "S01062.3000": 12, "S02012.1004": 8,
                       "S02012.2004": 8, "S11013.1000": 40, "S11013.2000": 36, "U00221.2000": 4,
                       "U00281.2000": 6, "U07021.2092": 4, "U10012.1000": 2, "U10012.2000": 2,
                       "U22011.0500": 4},
    (12.0, 1.0, 4.7): {"S01022.3000": 10, "S01032.0210": 10, "S01062.1500": 10, "S02012.1004": 2,
                       "S02012.3004": 8, "S11013.1000": 32, "S11013.3000": 79, "U00221.3000": 1,
                       "U00281.3000": 31, "U07021.2092": 1, "U10012.1000": 2, "U10012.3000": 8,
                       "U22011.0500": 10},
}


def counts(result) -> Counter:
    return Counter({r["article"]: r["qty"] for r in result["spec"]["rows"]})


class SplitTests(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(split_length(3000), [3000])
        self.assertEqual(split_length(12000), [3000] * 4)
        self.assertEqual(split_length(10000), [2500] * 4)

    def test_breakpoint_from_balcony(self):
        # башня 3.0 м, балкон шириной 1.5 м — нужна стойка на отметке 1.5
        self.assertEqual(split_length(3000, [1500]), [1500, 1500])


class ArchiveComparison(unittest.TestCase):
    """Сравнение с архивом. Полного совпадения не ждём — следим, чтобы не уехало."""

    def test_close_to_archive(self):
        for (L, W, H), arch in ARCHIVE.items():
            res = run(ConstructionInput(classify(L, W), L, W, H))
            gen = counts(res)
            total_a, total_g = sum(arch.values()), sum(gen.values())
            with self.subTest(size=f"{L}х{W}х{H}"):
                # допуск 20 %: по новым правилам промежуточные настилы полные, с люком,
                # и добавлен подъём на нижний ярус — в старых чертежах этого не было
                self.assertLess(abs(total_g - total_a) / total_a, 0.20,
                                f"всего элементов: генератор {total_g}, архив {total_a}")
                # опорные элементы должны совпадать точно
                for art in ("U22011.0500", "S01032.0210"):
                    self.assertEqual(gen[art], arch[art], art)


class BalconyRule(unittest.TestCase):
    """Случай из чертежа 2.0х1.0х4.2_2.0х1.0х-: балкон к башне."""

    def setUp(self):
        top = 4105
        st = Structure(xs=[0, 2000], ys=[0, 1000, 2000])
        # j=1 — башня на земле, j=0 — балкон без опоры на землю
        st.cells[(0, 1)] = Cell(0, 1, decks={1105, 3105}, top=top, access=True)
        st.cells[(0, 0)] = Cell(0, 0, decks={2605}, top=top, bottom=2105,
                                ground=False, role="balcony")
        self.st = st
        self.gen = generate(st)

    def ledgers_on_shared_edge(self):
        return sorted(e.z for e in self.gen.elements
                      if e.kind == "ledger" and e.rot == 0 and e.y == 1000)

    def test_guardrails_removed_on_shared_side(self):
        # как у вас в чертеже: 2105, 2605, 3105 есть; 3605 и 4105 сняты
        self.assertEqual(self.ledgers_on_shared_edge(), [105, 605, 1105, 1605, 2105, 2605, 3105])

    def test_no_toeboard_on_shared_side(self):
        shared = [e for e in self.gen.elements if e.kind == "toeboard" and e.rot == 0 and e.y == 1000]
        self.assertEqual(shared, [])

    def test_balcony_posts_hang(self):
        posts = [e for e in self.gen.elements if e.kind == "post" and e.y == 0]
        self.assertTrue(posts)
        self.assertTrue(all(e.z >= 2105 for e in posts))
        jacks = [e for e in self.gen.elements if e.kind == "jack" and e.y == 0]
        self.assertEqual(jacks, [])


class AccessRules(unittest.TestCase):
    """Правила подъёма, уточнённые на реальном примере."""

    def elements(self, L, W, H, kind="tower"):
        return run(ConstructionInput(kind, L, W, H))

    def test_short_post_on_top(self):
        res = self.elements(2, 1, 10.2)
        posts = sorted((e["z"], e["article"]) for e in res["elements"]
                       if e["kind"] == "post" and e["x"] == 0 and e["y"] == 0)
        self.assertEqual([a for _, a in posts],
                         ["S01022.3000", "S01062.3000", "S01062.3000", "S01062.1000"])

    def test_hatches_alternate_180(self):
        res = self.elements(2, 1, 10.2)
        hatches = sorted((e["z"], e["rot"]) for e in res["elements"] if e["kind"] == "hatch")
        rots = [r for _, r in hatches]
        self.assertEqual(len(rots), 4)
        self.assertTrue(all(a != b for a, b in zip(rots, rots[1:])), rots)

    def test_builtin_ladder_not_duplicated(self):
        # настилы с люком 3.0 м — лестница в блоке, отдельной быть не должно
        res = self.elements(3, 1, 6.7)
        hatch_z = {e["z"] for e in res["elements"] if e["article"] == "U00221.3000"}
        self.assertTrue(hatch_z)
        ladders_at_hatches = [e for e in res["elements"]
                              if e["kind"] == "ladder" and e["z"] - 36 in hatch_z]
        self.assertEqual(ladders_at_hatches, [])
        # для 2.0 м лестница отдельная — по одной на люк
        res = self.elements(2, 1, 10.2)
        hatch_z = {e["z"] for e in res["elements"] if e["kind"] == "hatch"}
        n_ladder = sum(e["kind"] == "ladder" and e["z"] - 36 in hatch_z for e in res["elements"])
        self.assertEqual(len(hatch_z), n_ladder)

    def test_no_ladder_below_zero(self):
        for H in (1.5, 2.7, 4.2, 4.7, 5.2, 6.2, 10.2):
            res = self.elements(3, 1, H)
            for e in res["elements"]:
                if e["kind"] == "hatch":
                    self.assertGreaterEqual(e["z"] - 2000, BASE_LEVEL, f"H={H}")

    def test_top_floor_is_one_and_half_metres(self):
        # 10.2: строим 10.0, верх 10105 (+0.2) -> настилы 605, 2605 … 8605 (+0.2) — как в архиве
        res = self.elements(2, 1, 10.2)
        self.assertEqual(res["grid"]["decks"], [805, 2805, 4805, 6805, 8805])
        self.assertEqual(res["grid"]["top"] - res["grid"]["decks"][-1], 1500)

    def test_lower_than_one_and_half_is_rejected(self):
        from tais.generator import SplitError
        with self.assertRaises(SplitError):
            self.elements(2, 1, 1.4)

    def test_ground_ladder_for_one_metre_floor(self):
        # 4.7: строим 4.5 (+0.2), верх 4605 -> настилы 1105 и 3105 -> нижний ярус 1.0 м
        res = self.elements(2, 1, 4.7)
        els = res["elements"]
        lift = res["grid"]["lift"]
        self.assertEqual(lift, 200)
        zero = sorted(e["y"] for e in els if e["kind"] == "deck" and e["z"] == BASE_LEVEL + lift)
        self.assertEqual(zero, [500, 750])            # две полосы со стороны y1 на нуле
        low = [e for e in els if e["kind"] == "deck" and e["z"] == 1105 + lift]
        self.assertEqual(len(low), 2)                 # из 4 полос на ярусе осталось 2
        ground = [e for e in els if e["kind"] == "ladder" and e["z"] == BASE_LEVEL + lift + 2000 + 36]
        self.assertEqual(len(ground), 1)
        # у ригеля стороны x0, спуск в сторону +X, ширина внутри полос y 500…1000
        self.assertEqual((ground[0]["x"], ground[0]["y"], ground[0]["rot"]), (242 - 216, 562, 90))
        self.assertFalse(any("Нижний ярус" in w for w in res["warnings"]))

    def test_half_metre_floor_is_a_step(self):
        # 4.2: строим 4.0 (+0.2), верх 4105 -> настилы 605 и 2605 (+0.2) -> нижний ярус 0.5 м
        res = self.elements(3, 1, 4.2)
        self.assertEqual(res["grid"]["decks"], [805, 2805])
        ground_z = BASE_LEVEL + res["grid"]["lift"] + 2000 + 36
        self.assertFalse(any(e["kind"] == "ladder" and e["z"] == ground_z for e in res["elements"]))
        self.assertFalse(any("Нижний ярус" in w for w in res["warnings"]))


class EntranceAndDiagonals(unittest.TestCase):
    def test_entrance_opening(self):
        res = run(ConstructionInput("tower", 2, 2, 6.0))
        lift = res["grid"]["lift"]
        front = [e for e in res["elements"] if e["kind"] in ("ledger", "toeboard")
                 and e["rot"] == 0 and e["y"] == 0 and e["x"] == 0]
        # ниже 2 м на грани с наименьшим Y в пролёте входа нет ригелей и бортиков
        self.assertFalse([e for e in front if e["z"] - lift < BASE_LEVEL + 2000])
        # диагонали вход не трогает
        self.assertTrue([e for e in res["elements"] if e["kind"] == "diagonal"
                         and e["y"] == 0 and e["rot"] == 0 and e["z"] - lift < BASE_LEVEL + 2000])
        # ригель-перемычка на 2 м остаётся
        self.assertTrue([e for e in front if e["kind"] == "ledger" and e["z"] - lift == BASE_LEVEL + 2000])
        # без входной группы ригели внизу на месте
        closed = run(ConstructionInput("tower", 2, 2, 6.0, entrance=False))
        self.assertTrue([e for e in closed["elements"] if e["kind"] == "ledger" and e["rot"] == 0
                         and e["y"] == 0 and e["z"] == BASE_LEVEL])

    def test_entrance_moves_to_ladder_side(self):
        # 4.7: нижний ярус 1.0 м, нужна лестница с земли -> вход на грани с наибольшим Y
        res = run(ConstructionInput("tower", 2, 1, 4.7))
        lift = res["grid"]["lift"]
        low = lambda y: [e for e in res["elements"] if e["kind"] == "ledger" and e["rot"] == 0
                         and e["y"] == y and e["x"] == 0 and e["z"] - lift < BASE_LEVEL + 2000]
        self.assertEqual(low(1000), [])   # проём со стороны лестницы
        self.assertTrue(low(0))           # грань с наименьшим Y закрыта

    def test_opposite_diagonals_point_opposite_ways(self):
        res = run(ConstructionInput("tower", 2, 2, 6.0, entrance=False))
        diag = [e for e in res["elements"] if e["kind"] == "diagonal"]

        def rise(e):  # куда смещается верх диагонали в плане
            (x1, y1, _), (x2, y2, _) = e["seg"]
            return (x2 - x1, y2 - y1)

        y_low = {rise(e) for e in diag if e["seg"][0][1] == e["seg"][1][1] == 0}
        y_high = {rise(e) for e in diag if e["seg"][0][1] == e["seg"][1][1] == 2000}
        x_low = {rise(e) for e in diag if e["seg"][0][0] == e["seg"][1][0] == 0}
        x_high = {rise(e) for e in diag if e["seg"][0][0] == e["seg"][1][0] == 2000}
        self.assertEqual(y_low, {(2000, 0)})
        self.assertEqual(y_high, {(-2000, 0)})
        self.assertEqual(x_low, {(0, -2000)})
        self.assertEqual(x_high, {(0, 2000)})


class HeightRule(unittest.TestCase):
    """Высота акта не кратна 0.5 м: строим кратную и сдвигаем всё, кроме домкратов."""

    def test_plan(self):
        from tais.generator.constructions import height_plan
        self.assertEqual(height_plan(6000), (6000, 0))
        self.assertEqual(height_plan(6100), (6000, 100))
        self.assertEqual(height_plan(6200), (6000, 200))
        self.assertEqual(height_plan(6300), (6000, 300))
        self.assertEqual(height_plan(6400), (6500, -100))

    def test_jacks_stay_rest_moves(self):
        base = run(ConstructionInput("tower", 2, 2, 6.0))
        up = run(ConstructionInput("tower", 2, 2, 6.2))
        down = run(ConstructionInput("tower", 2, 2, 6.4))
        for res in (base, up, down):
            self.assertTrue(all(e["z"] == 0 for e in res["elements"] if e["kind"] == "jack"))
        z_start = lambda r: {e["z"] for e in r["elements"] if e["kind"] == "starter"}
        self.assertEqual(z_start(base), {0})
        self.assertEqual(z_start(up), {200})
        self.assertEqual(z_start(down), {-100})
        # 6.2 и 6.0 — одна и та же конструкция, только поднята
        self.assertEqual(counts(base), counts(up))
        self.assertEqual(up["grid"]["top"], base["grid"]["top"] + 200)


if __name__ == "__main__":
    unittest.main()


class WideningRules(unittest.TestCase):
    """Уширение: без настилов и перил, ригели через 2 м от нижнего узла и на верху,
    с одной стороны своих стоек нет — ригели крепятся к существующим стойкам."""

    def scheme(self, items):
        from tais.generator.scheme import run_scheme
        return run_scheme(items)

    @staticmethod
    def x_ledgers(res, y):
        return sorted({e["z"] for e in res["elements"]
                       if e["kind"] == "ledger" and e["rot"] == 0 and e["y"] == y})

    def test_standalone(self):
        res = self.scheme([{"kind": "widening", "length": 3, "width": 1, "height": 5}])
        kinds = Counter(e["kind"] for e in res["elements"])
        self.assertEqual(kinds["deck"] + kinds["hatch"] + kinds["toeboard"] + kinds["ladder"], 0)
        # стойки только на дальней стороне (y = 1000)
        self.assertEqual({e["y"] for e in res["elements"] if e["kind"] == "post"}, {1000})
        self.assertEqual(kinds["jack"], 2)
        # отметки 0, 2, 4 и 5 м от нижнего узла
        self.assertEqual(self.x_ledgers(res, 1000), [105, 2105, 4105, 5105])
        self.assertEqual(self.x_ledgers(res, 0), [])   # ригели открытой стороны — у стоящей конструкции
        ys = sorted({e["z"] for e in res["elements"] if e["kind"] == "ledger" and e["rot"] == 270})
        self.assertEqual(ys, [105, 2105, 4105, 5105])

    def test_attached_on_existing_posts(self):
        res = self.scheme([
            {"kind": "tower", "length": 3, "width": 1, "height": 6},
            {"kind": "widening", "length": 3, "width": 1, "height": 5,
             "attach_to": 1, "side": "y0", "offset": 0},
        ])
        self.assertEqual(len(res["parts"]), 1)
        g = res["parts"][0]["grid"]
        self.assertEqual(g["xs"], [0, 3000])
        self.assertEqual(g["ys"], [0, 1000, 2000])
        # стойки на дальней стороне уширения и у основной; лишних стоек нет
        posts = {(e["x"], e["y"]) for e in res["elements"] if e["kind"] == "post"}
        self.assertEqual(posts, {(x, y) for x in (0, 3000) for y in (0, 1000, 2000)})
        self.assertEqual(self.x_ledgers(res, 0), [105, 2105, 4105, 5105])
        # общая сторона: наружная обшивка основной конструкции остаётся
        self.assertEqual(self.x_ledgers(res, 1000), list(range(105, 6106, 500)))
        # вход закрыт уширением — перенесён на заднюю сторону
        self.assertTrue(any("перенесена" in w for w in res["warnings"]))

    def test_main_rebuilt_to_fit_posts(self):
        res = self.scheme([
            {"kind": "tower", "length": 3, "width": 2, "height": 6.2},
            {"kind": "widening", "length": 1.5, "width": 1, "height": 5,
             "attach_to": 1, "side": "y1", "offset": 1.5},
        ])
        g = res["parts"][0]["grid"]
        self.assertEqual(g["bays_x"], [1500, 1500])
        self.assertTrue(any("перестроена" in w for w in res["warnings"]))
        # сдвиг основной +0.2 м — ригели уширения на её узлах
        self.assertEqual(g["widening_levels"], [305, 2305, 4305, 5305])

    def test_back_face_diagonals_stay_mirrored(self):
        res = self.scheme([
            {"kind": "tower", "length": 3, "width": 1, "height": 6},
            {"kind": "widening", "length": 3, "width": 1, "height": 5,
             "attach_to": 1, "side": "y0", "offset": 0},
        ])
        back = {e["rot"] for e in res["elements"]
                if e["kind"] == "diagonal" and e["y"] == 2000 and e["rot"] in (0, 180)}
        self.assertEqual(back, {180})

    def test_errors(self):
        tower = {"kind": "tower", "length": 3, "width": 1, "height": 6}
        with self.assertRaises(SplitError):
            self.scheme([tower, {"kind": "widening", "length": 3, "width": 1, "height": 5,
                                 "attach_to": 1, "side": "y0", "offset": 1}])
        with self.assertRaises(SplitError):
            self.scheme([tower, {"kind": "widening", "length": 3, "width": 1, "height": 5,
                                 "attach_to": 5}])


class BalconyAttachRules(unittest.TestCase):
    """Консольно-опорные леса (балкон): верхний настил продлён наружу, стойки 2 м снаружи,
    внутри своих стоек нет, под каждой стойкой — диагональ к конструкции, бортики,
    перила основной на общей стороне сняты."""

    def scheme(self, items):
        from tais.generator.scheme import run_scheme
        return run_scheme(items)

    @staticmethod
    def ledgers(res, y):
        return sorted({e["z"] for e in res["elements"]
                       if e["kind"] == "ledger" and e["rot"] == 0 and e["y"] == y})

    def setUp(self):
        self.res = self.scheme([
            {"kind": "tower", "length": 3, "width": 1, "height": 6},
            {"kind": "balcony", "length": 3, "width": 1, "height": 6,
             "attach_to": 1, "side": "y0", "offset": 0},
        ])
        self.els = self.res["elements"]

    def test_posts_two_metres_outside_only(self):
        posts = [e for e in self.els if e["kind"] == "post" and e["y"] == 0]
        self.assertEqual({(e["article"], e["z"]) for e in posts}, {("S01062.2000", 4105)})
        self.assertEqual(len(posts), 2)
        self.assertFalse(any(e["kind"] == "jack" and e["y"] == 0 for e in self.els))

    def test_deck_continues_top_deck(self):
        decks = {e["z"] for e in self.els if e["kind"] == "deck" and e["y"] < 1000}
        self.assertEqual(decks, {4605})

    def test_guardrails_removed_for_access(self):
        # нижнего ряда ригелей у балкона нет — ригели от настила
        self.assertEqual(self.ledgers(self.res, 0), [4605, 5105, 5605, 6105])
        shared = self.ledgers(self.res, 1000)
        for z in (5105, 5605, 6105):
            self.assertNotIn(z, shared)
        self.assertIn(4605, shared)

    def test_toeboards_on_balcony_edge(self):
        toes = {(e["rot"], e["y"]) for e in self.els if e["kind"] == "toeboard"}
        self.assertIn((0, 0), toes)        # наружный край балкона
        self.assertNotIn((0, 1000), toes)  # общий край — настил с двух сторон

    def test_brace_under_each_post(self):
        braces = [e for e in self.els if e["kind"] == "diagonal" and e["rot"] == 270
                  and e["y"] == 1000 and e["seg"][1][1] == 0]
        self.assertEqual(sorted(e["x"] for e in braces), [0, 3000])
        # диагональ поднята на 0.5 м: от 2605 на стойке башни до настила балкона 4605
        self.assertTrue(all(e["article"] == "S02012.1004" and e["z"] == 2605
                            and e["seg"][1][2] == 4605 for e in braces))

    def test_standalone(self):
        res = self.scheme([{"kind": "balcony", "length": 3, "width": 1, "height": 6}])
        els = res["elements"]
        self.assertEqual({e["y"] for e in els if e["kind"] == "post"}, {1000})
        self.assertEqual(self.ledgers(res, 0), [])
        self.assertFalse(any(e["kind"] == "toeboard" and e["rot"] == 0 and e["y"] == 0 for e in els))
        self.assertEqual(sum(e["kind"] == "diagonal" for e in els), 2)

    def test_width_must_be_one_bay(self):
        with self.assertRaises(SplitError):
            self.scheme([{"kind": "balcony", "length": 3, "width": 3.5, "height": 6}])

    def test_area_uses_two_metres(self):
        from tais.acts import area
        a = area([{"kind": "tower", "length": 3, "height": 6},
                  {"kind": "balcony", "length": 3, "height": 6}])
        self.assertEqual(a["value"], 24.0)


class BalconyOverWidening(unittest.TestCase):
    """Балкон и уширение на одной стороне: не пересекаются по высоте, если уширение
    не выше высоты основной − 3.5 м (балкон 1.5 м + диагональ 2.0 м)."""

    def scheme(self, wid_h):
        from tais.generator.scheme import run_scheme
        return run_scheme([
            {"kind": "facade", "length": 6, "width": 1, "height": 18},
            {"kind": "balcony", "length": 6, "width": 1, "height": 0,
             "attach_to": 1, "side": "y0", "offset": 0},
            {"kind": "widening", "length": 3, "width": 1, "height": wid_h,
             "attach_to": 1, "side": "y0", "offset": 0},
        ])

    def test_allowed_below_limit(self):
        res = self.scheme(4)
        posts = sorted((e["z"], e["z"] + int(e["article"][-4:])) for e in res["elements"]
                       if e["kind"] == "post" and e["x"] == 0 and e["y"] == 0)
        # стойки уширения от земли до 4105, стойки балкона 16105…18105 — отдельно
        self.assertEqual(posts[0][0], 105)
        self.assertEqual(posts[-1], (16105, 18105))
        self.assertTrue(all(b <= 4105 or a >= 16105 for a, b in posts))
        self.assertEqual(sum(e["kind"] == "jack" and e["y"] == 0 for e in res["elements"]), 2)

    def test_limit(self):
        self.scheme(14.5)                      # 18 − 3.5 — ещё можно
        with self.assertRaises(SplitError):
            self.scheme(15)


class DifferentReachOneSide(unittest.TestCase):
    """Пристройки на одной стороне с разным выносом: балкон 2 м над уширением 3 м.
    Пролёт уширения не режется линией балкона — ригели и диагонали целые (3 м)."""

    def test_widening_keeps_full_bay(self):
        from tais.generator.scheme import run_scheme
        res = run_scheme([
            {"kind": "tower", "length": 3, "width": 2, "height": 10},
            {"kind": "balcony", "length": 3, "width": 2, "height": 0,
             "attach_to": 1, "side": "y0", "offset": 0},
            {"kind": "balcony", "length": 3, "width": 1, "height": 0,
             "attach_to": 1, "side": "y1", "offset": 0},
            {"kind": "widening", "length": 3, "width": 3, "height": 4,
             "attach_to": 1, "side": "y0", "offset": 0},
        ])
        els = res["elements"]
        front = [e for e in els if e["kind"] == "ledger" and e["rot"] == 270 and e["x"] == 0
                 and e["seg"][0][1] < 3000]
        low = sorted((e["article"], e["z"]) for e in front if e["z"] < 5000)
        self.assertEqual(low, [("S11013.3000", 105), ("S11013.3000", 2105), ("S11013.3000", 4105)])
        high = {e["article"] for e in front if e["z"] > 8000}
        self.assertEqual(high, {"S11013.2000"})
        # стойки балкона 2 м — подвесные на линии своего выноса, стойки уширения — от земли
        posts = {(e["y"], e["z"]) for e in els if e["kind"] == "post" and e["x"] == 0 and e["y"] < 3000}
        self.assertIn((1000, 8105), posts)
        self.assertIn((0, 105), posts)
        self.assertFalse(any(e["kind"] == "ledger" and e["seg"][0][1] == 1000 and e["seg"][1][1] == 1000
                             and e["z"] < 5000 for e in els))


class RadialTests(unittest.TestCase):
    """Радиальные леса: кольцо из повёрнутых ячеек с общими внутренними стойками."""

    def ring(self, length, width=1.0, height=6.2, **kw):
        return run(ConstructionInput("radial", length, width, height, **kw))

    def test_cells_sum_to_length(self):
        r = self.ring(24)
        self.assertEqual(sum(r["grid"]["bays_x"]), 24000)
        self.assertEqual(r["grid"]["bays_x"], [3000] * 8)
        self.assertEqual(r["grid"]["radial"]["turn"], [45.0])

    def test_shared_inner_posts_and_inserts(self):
        r = self.ring(24)
        c = counts(r)
        # 8 внутренних стоек (общие) + 16 наружных (расходятся)
        self.assertEqual(c["S01032.0210"], 24)
        # наружный зазор 2·1.0·sin(22.5°) = 0.765 → вставка 0.75 м на 13 отметках обшивки в 8 стыках
        self.assertEqual(c["S11013.0750"], 8 * 13)
        self.assertEqual(c["U10012.0750"], 8)
        # поперечные ригели — по 2 на ячейку (у каждой своя пара), на нижнем узле и под 3 настилами
        self.assertEqual(c["S11013.1000"], 8 * 2 * 4)
        # диагонали — снаружи и изнутри каждой ячейки, 2 полных яруса
        self.assertEqual(c["S02012.3004"], 8 * 2 * 2)

    def test_ledgers_end_on_posts(self):
        import math
        r = self.ring(30, height=10)
        posts = {(round(e["x"]), round(e["y"])) for e in r["elements"] if e["kind"] == "post"}

        def on_post(p):
            return any(math.hypot(p[0] - q[0], p[1] - q[1]) < 2 for q in posts)
        loose = [e for e in r["elements"] if e["kind"] in ("ledger", "diagonal", "toeboard")
                 and not all(on_post(p) for p in e["seg"])]
        inserts = {f"S11013.{size:04d}" for size, _ in r["grid"]["radial"]["inserts"]} | \
                  {f"U10012.{size:04d}" for size, _ in r["grid"]["radial"]["inserts"]}
        # не на стойках — только вставки (по центру зазора, разница — в предупреждении)
        self.assertTrue(all(e["article"] in inserts for e in loose))

    def test_big_ring_turns_every_few_cells(self):
        # 200 м: зазор у одной ячейки меньше 0.25 м — поворот через несколько ячеек
        r = self.ring(200, height=8)
        rad = r["grid"]["radial"]
        self.assertGreater(rad["per_section"], 1)
        self.assertLessEqual(rad["max_dev"], 50)

    def test_widening_outward(self):
        r = self.ring(60, width=2.0, height=20, widening=True, widening_width=1.0, widening_height=8)
        self.assertEqual(r["grid"]["bays_y"], [1000, 2000])
        self.assertTrue(r["grid"]["widening_levels"])
        # две линии наружных вставок: у основной и у уширения
        self.assertEqual(len({d for _, d in r["grid"]["radial"]["inserts"]}), 2)

    def test_wedge_planks(self):
        # 24 м: клин 45°, по 2 планки 1.0 м в каждом из 8 стыков на каждом из 3 настилов
        r = self.ring(24)
        self.assertEqual(counts(r)["U00141.1000"], 2 * 8 * 3)
        self.assertTrue(any("щель до 0.301 м" in w for w in r["warnings"]))
        # 30 м: клин 30° закрывается почти полностью — без предупреждения
        r = self.ring(30, height=10)
        self.assertEqual(counts(r)["U00141.1000"], 3 * 12 * 5)
        self.assertFalse(any("щель" in w for w in r["warnings"]))

    def test_area_is_length_by_height(self):
        r = self.ring(24, height=6.2)
        self.assertAlmostEqual(r["area"]["value"], 24 * 6.2)

    def test_too_short(self):
        with self.assertRaises(SplitError):
            self.ring(2.5)

    def test_scheme_cannot_attach_to_radial(self):
        from tais.generator.scheme import run_scheme
        with self.assertRaises(SplitError):
            run_scheme([{"kind": "radial", "length": 24, "width": 1, "height": 6},
                        {"kind": "widening", "length": 3, "width": 1, "height": 4, "attach_to": 1}])
        res = run_scheme([{"kind": "radial", "length": 24, "width": 1, "height": 6},
                          {"kind": "tower", "length": 2, "width": 2, "height": 4}])
        self.assertEqual(len(res["parts"]), 2)
