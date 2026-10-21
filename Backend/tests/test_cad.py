"""Подкладки и ошибка кэша gen_py (без nanoCAD)."""
from __future__ import annotations

import os
import tempfile
import unittest

from tais.cad import nanocad
from tais.generator import ConstructionInput, run


class Pads(unittest.TestCase):
    def test_pad_under_each_jack_first_in_spec(self):
        res = run(ConstructionInput("facade", 6, 1, 4.2, pads=True))
        qty = {r["article"]: r["qty"] for r in res["spec"]["rows"]}
        self.assertEqual(qty["U22061.0300"], qty["U22011.0500"])
        self.assertEqual(res["spec"]["rows"][0]["article"], "U22061.0300")

    def test_pads_off_by_default(self):
        res = run(ConstructionInput("facade", 6, 1, 4.2))
        self.assertNotIn("U22061.0300", {r["article"] for r in res["spec"]["rows"]})


class PrintFiles(unittest.TestCase):
    def test_pdf_device_and_names(self):
        self.assertTrue(nanocad.is_file_device("Microsoft Print to PDF"))
        self.assertTrue(nanocad.is_file_device("PDF (встроенный)"))
        self.assertFalse(nanocad.is_file_device("HP LaserJet M404"))
        out = os.path.join("C:", os.sep, "TAIS")
        self.assertEqual(nanocad.pdf_name(os.path.join(out, "DWG", "ИС7.dwg")),
                         os.path.join(out, "PDF", "ИС7.pdf"))
        self.assertEqual(nanocad.pdf_name(os.path.join(out, "ИС7.dwg")),
                         os.path.join(out, "PDF", "ИС7.pdf"))

    def test_merge_two_sheets_into_one_pdf(self):
        try:
            from pypdf import PdfWriter
        except ImportError:
            self.skipTest("нет pypdf")
        with tempfile.TemporaryDirectory() as tmp:
            parts = []
            for name, (w, h) in (("A3", (1191, 842)), ("A4", (595, 842))):
                part = os.path.join(tmp, f"s_{name}.pdf")
                wr = PdfWriter()
                wr.add_blank_page(w, h)
                with open(part, "wb") as f:
                    wr.write(f)
                parts.append(part)
            target = os.path.join(tmp, "s.pdf")
            self.assertTrue(nanocad.merge_pdfs(parts, target))
            self.assertEqual(nanocad.pdf_pages(target), 2)


class GenPy(unittest.TestCase):
    def test_detect(self):
        err = AttributeError("module 'win32com.gen_py.ABCD-1234x0x1x0' has no attribute 'CLSIDToClassMap'")
        self.assertTrue(nanocad.is_gen_py_error(err))
        self.assertFalse(nanocad.is_gen_py_error(ValueError("Файл не найден")))
        self.assertEqual(nanocad.gen_py_error().code, "gen_py_cache")

    def test_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("TEMP")
            os.environ["TEMP"] = tmp
            try:
                gp = os.path.join(tmp, "gen_py", "3.10")
                os.makedirs(gp)
                open(os.path.join(gp, "dicts.dat"), "w").close()
                res = nanocad.clear_gen_py()
                self.assertFalse(os.path.exists(os.path.join(tmp, "gen_py")))
                self.assertEqual(res["failed"], [])
            finally:
                if old is None:
                    os.environ.pop("TEMP", None)
                else:
                    os.environ["TEMP"] = old


if __name__ == "__main__":
    unittest.main()


class FakeSpdsTable:
    ObjectName = "mcsDbObjectTable2"

    def __init__(self):
        self.Visible = True
        self.deleted = False

    def Delete(self):
        self.deleted = True


class FakeEnt:
    def __init__(self, kind, *args):
        self.kind, self.args = kind, args
        self.Layer = "0"


class FakeBlock:
    def __init__(self, ents):
        self._items = list(ents)
        self.lines, self.texts = [], []

    @property
    def Count(self):
        return len(self._items)

    def Item(self, i):
        return self._items[i]

    def AddLine(self, a, b):
        e = FakeEnt("line", a, b)
        self.lines.append((tuple(a), tuple(b)))
        return e

    def AddMText(self, p, w, text):
        e = FakeEnt("mtext", p, w, text)
        self.texts.append(text)
        return e


class _Layout:
    def __init__(self, name, block):
        self.Name = name
        self.Block = block


class _Coll:
    def __init__(self, items):
        self._items = items
        self.Count = len(items)

    def Item(self, i):
        return self._items[i]

    def Add(self, name):
        return name


class FakeDoc:
    def __init__(self, block):
        self.Layouts = _Coll([_Layout("Model", FakeBlock([])), _Layout("A4", block)])
        self.Layers = _Coll([])


class DrawnSpecTable(unittest.TestCase):
    def setUp(self):
        self._point = nanocad._point
        nanocad._point = lambda x, y, z: (round(x, 3), round(y, 3), z)

    def tearDown(self):
        nanocad._point = self._point

    def spec(self, n):
        rows = [{"article": f"A{i}", "name": f"Имя {i}", "qty": i + 1, "unit_weight": 1.5}
                for i in range(n)]
        return {"rows": rows, "total_weight": 123.45}

    def test_draws_grid_and_hides_spds_table(self):
        table = FakeSpdsTable()
        block = FakeBlock([table])
        info = nanocad._spec_table(FakeDoc(block), self.spec(13))
        self.assertTrue(info["ok"], info)
        self.assertFalse(table.Visible)          # скрыта
        self.assertFalse(table.deleted)          # но не удалена
        # 15 строк (заголовок + 13 + «Итого») -> 16 горизонтальных и 5 вертикальных линий
        self.assertEqual(len(block.lines), 16 + 5)
        ys = sorted({a[1] for a, b in block.lines if a[1] == b[1]}, reverse=True)
        self.assertEqual((ys[0], ys[-1]), (277.7, 157.7))   # как в PDF
        xs = sorted({a[0] for a, b in block.lines if a[0] == b[0]})
        self.assertEqual(xs, [20.0, 43.4, 142.5, 172.8, 205.0])
        self.assertIn("Итого, кг", block.texts)
        self.assertIn("123,45", block.texts)
        self.assertIn("1,5", block.texts)

    def test_small_rows_over_24(self):
        block = FakeBlock([FakeSpdsTable()])
        info = nanocad._spec_table(FakeDoc(block), self.spec(25))   # 27 строк
        self.assertEqual(info["row_height"], 6.0)
