"""Работа с nanoCAD через COM (только Windows).

* status()  — установлен ли nanoCAD, какая версия, запущен ли.
* build()   — открыть шаблон, сохранить копию, заменить модель, сохранить.
* show()    — сделать окно nanoCAD с готовой схемой активным.
* print_file() — распечатать листы схемы (A3, A4): на принтер или, если принтер PDF, в PDF (подпапка
  PDF рядом с DWG) без окна сохранения; по желанию закрыть файл с сохранением.
* printers()  — список принтеров nanoCAD для настроек.

COM-объекты живут в одном выделенном потоке (ComWorker): FastAPI обрабатывает
запросы в разных потоках, а COM-объект нельзя передавать между потоками.

Внимание: этот модуль ещё не проверен на живом nanoCAD — проверяется
на Windows-машине (см. README, раздел «Проверка nanoCAD»).
"""
from __future__ import annotations

import logging
import math
import os
import queue
import re
import shutil
import sys
import tempfile
import threading
import traceback
from concurrent.futures import Future
from pathlib import Path

from . import views

log = logging.getLogger("tais.cad")

PROGID = "nanoCAD.Application"
ARTICLE_RE = re.compile(r"^([SU]\d{5}\.\d{4})\b")


class CadError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# --------------------------------------------------------- кэш gen_py -----
# pywin32 хранит сгенерированные обёртки COM в %TEMP%\gen_py. Если кэш испорчен
# (обновился nanoCAD, прервалась генерация), вызовы падают с ошибками про gen_py,
# CLSIDToClassMap и т.п. Лечится удалением папки и перезапуском TAIS и nanoCAD.
GEN_PY_MARKERS = ("gen_py", "clsidtoclassmap", "clsidtopackagemap", "makepy", "gencache")
GEN_PY_MESSAGE = (
    "Повреждён кэш COM-обёрток (папка gen_py). Нужно удалить папку {path}, "
    "закрыть nanoCAD и перезапустить TAIS. Кнопка «Очистить и перезапустить» "
    "сделает первое и последнее сама — nanoCAD закройте вручную, сохранив открытые чертежи."
)


def gen_py_dir() -> Path:
    temp = os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()
    return Path(temp) / "gen_py"


def is_gen_py_error(exc: BaseException) -> bool:
    text = (repr(exc) + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))).lower()
    return any(m in text for m in GEN_PY_MARKERS)


def gen_py_error() -> "CadError":
    return CadError("gen_py_cache", GEN_PY_MESSAGE.format(path=gen_py_dir()))


def clear_gen_py() -> dict:
    """Удалить кэш gen_py. Процесс TAIS после этого нужно перезапустить."""
    paths = {gen_py_dir()}
    try:
        import win32com

        gp = getattr(win32com, "__gen_path__", None)
        if gp:
            paths.add(Path(gp))
    except Exception:
        pass
    removed, failed = [], []
    for p in paths:
        if p.exists():
            try:
                shutil.rmtree(p)
                removed.append(str(p))
            except OSError as exc:
                failed.append(f"{p}: {exc}")
    return {"removed": removed, "failed": failed}


# ------------------------------------------------------------------ реестр --
def registry_info() -> dict:
    """Ищем nanoCAD в реестре без запуска программы."""
    info = {"installed": False, "progid": PROGID, "version": None}
    if sys.platform != "win32":
        return info
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, PROGID + r"\CLSID"):
            info["installed"] = True
    except OSError:
        return info
    try:
        cur = winreg.QueryValue(winreg.HKEY_CLASSES_ROOT, PROGID + r"\CurVer")
        info["version"] = cur.replace(PROGID + ".", "") or None
    except OSError:
        pass
    return info


# --------------------------------------------------------------- COM-поток --
class ComWorker:
    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _ensure(self) -> None:
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, name="nanocad-com", daemon=True)
                self._thread.start()

    def _loop(self) -> None:
        import pythoncom

        pythoncom.CoInitialize()
        while True:
            fn, args, fut = self._q.get()
            if fut.set_running_or_notify_cancel():
                try:
                    fut.set_result(fn(*args))
                except BaseException as exc:  # передаём ошибку в вызывающий поток
                    fut.set_exception(exc)

    def call(self, fn, *args, timeout: float | None = None):
        self._ensure()
        fut: Future = Future()
        self._q.put((fn, args, fut))
        return fut.result(timeout=timeout)


_worker = ComWorker()


def _active_app():
    import win32com.client

    try:
        return win32com.client.GetActiveObject(PROGID)
    except Exception:
        return None


def _get_or_start_app():
    import win32com.client

    app = _active_app()
    if app is None:
        log.info("Запускаю nanoCAD")
        app = win32com.client.Dispatch(PROGID)
    try:
        app.Visible = True
    except Exception:
        pass
    return app


# ------------------------------------------------------------------ status --
def status() -> dict:
    info = registry_info()
    info["platform_ok"] = sys.platform == "win32"
    info["running"] = False
    if info["installed"]:
        try:
            info["running"] = _worker.call(lambda: _active_app() is not None, timeout=5)
        except Exception as exc:
            log.warning("Не удалось проверить запуск nanoCAD: %s", exc)
            if is_gen_py_error(exc):
                info["gen_py_error"] = gen_py_error().message
    return info


def require_installed() -> None:
    if sys.platform != "win32":
        raise CadError("nanocad_unsupported_os", "Работа с nanoCAD возможна только в Windows.")
    if not registry_info()["installed"]:
        raise CadError(
            "nanocad_not_installed",
            "На этом компьютере не найден nanoCAD. Установите nanoCAD, чтобы формировать "
            "чертежи; расчёт и спецификация работают и без него.",
        )


# ------------------------------------------------------------------- build --
def _point(x: float, y: float, z: float):
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, (float(x), float(y), float(z)))


def _block_names(doc) -> dict[str, str]:
    """артикул -> полное имя блока (берём самое длинное: оно с наименованием)."""
    out: dict[str, str] = {}
    for i in range(doc.Blocks.Count):
        name = doc.Blocks.Item(i).Name
        m = ARTICLE_RE.match(name)
        if m and len(name) > len(out.get(m.group(1), "")):
            out[m.group(1)] = name
    return out


def _model_space(doc):
    try:
        return doc.ModelSpace
    except Exception:
        return doc.Layouts.Item("Model").Block


def _replace_texts(doc, fields: dict[str, str]) -> int:
    """Заменить метки [Date], [Act]… во всех листах и в модели (как в ORG_V5)."""
    import win32com.client

    replaced = 0
    for k in range(doc.Layouts.Count):
        block = doc.Layouts.Item(k).Block
        for i in range(block.Count):
            ent = block.Item(i)
            if ent.ObjectName not in ("AcDbText", "AcDbMText"):
                continue
            # сначала обычный (позднее) связывание — без кэша gen_py; CastTo — запасной путь
            try:
                text = ent
                value = text.TextString
            except Exception:
                text = win32com.client.CastTo(ent, "IAcadText")
                value = text.TextString
            new = value
            for key, val in fields.items():
                new = new.replace(key, val)
            if new != value:
                text.TextString = new
                replaced += 1
    return replaced


def _layout_block(doc, name: str):
    for k in range(doc.Layouts.Count):
        lay = doc.Layouts.Item(k)
        if lay.Name == name:
            return lay.Block
    return None


def _area_table(doc, rows: list[dict], area_text: str, layout: str = "A3") -> bool:
    """Таблица «Габариты установленных лесов» — перенос table_first из ORG_V5."""
    block = _layout_block(doc, layout)
    if block is None or not rows:
        return False
    n = len(rows)
    table = block.AddTable(_point(30, 120, 0), n + 2, 3, 1, 70)
    table.SetText(0, 0, "Габариты установленных лесов")
    for col, title in enumerate(("Длина, м", "Ширина, м", "Высота, м")):
        table.SetText(1, col, title)
    for r, c in enumerate(rows):
        table.SetText(2 + r, 0, f"{c['length']:g}")
        table.SetText(2 + r, 1, f"{c['width']:g}")
        table.SetText(2 + r, 2, f"{c['height']:g}")
    table.InsertRows(n + 2, 1, 1)
    txt = "Площадь, м.кв. = " + area_text
    table.SetText(n + 2, 0, txt)
    table.SetCellAlignment(n + 2, 0, 1)
    for i in range(n + 3):
        for j in range(3):
            table.SetCellTextStyle(i, j, "ГОСТ 2.304")
            table.SetCellTextHeight(i, j, 2.5)
    table.MergeCells(n + 2, n + 2, 0, 2)
    for j in range(3):
        table.SetColumnWidth(j, 25)
    table.SetRowHeight(n + 2, 4.5 * (1 + len(txt) // 40))
    return True


# Таблица спецификации на листе A4 (таблица шаблона, перезаполняется)
SPEC_LAYOUT = "A4"
SPEC_TOP = 277.7            # верх таблицы, как в шаблоне
SPEC_TOP_MAX = 287.0        # если строки не помещаются — таблица поднимается сюда
SPEC_BOTTOM_MIN = 65.0      # ниже — основная надпись
SPEC_ROW = 8.0
SPEC_ROW_SMALL = 6.0        # если строк в таблице больше SPEC_ROWS_LIMIT
SPEC_ROWS_LIMIT = 24


def spec_layout(n_rows: int) -> tuple[float, float]:
    """(верх, высота строки). Строки по 8 мм; если строк больше 24 — по 6 мм.
    Если таблица всё равно не помещается над основной надписью — поднимаем её."""
    row = SPEC_ROW if n_rows <= SPEC_ROWS_LIMIT else SPEC_ROW_SMALL
    top = SPEC_TOP if SPEC_TOP - n_rows * row >= SPEC_BOTTOM_MIN else SPEC_TOP_MAX
    return top, row


def _num(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")


# --- таблица спецификации: линии + текст на месте таблицы СПДС шаблона ------
# Таблица СПДС (mcsDbObjectTable2) через COM не редактируется — она скрывается,
# а на её месте рисуется сетка линиями и текст. Размеры — с PDF-спецификации, мм листа.
SPEC_LEFT = 20.0
SPEC_COLS = (23.4, 99.1, 30.3, 32.2)
SPEC_HEADER = ("Артикул", "Наименование", "Количество", "Вес одного изделия, кг/шт")
SPEC_TEXT = {SPEC_ROW: 2.5, SPEC_ROW_SMALL: 2.2}   # высота текста для строк 8 и 6 мм
SPEC_PAD = 1.0                                     # отступ текста от линии, мм
SPEC_LAYER = "TAIS_Спецификация"
ATTACH_MIDDLE_LEFT = 4                             # acAttachmentPointMiddleLeft
ATTACH_MIDDLE_CENTER = 5                           # acAttachmentPointMiddleCenter


def _find_template_table(doc):
    block = _layout_block(doc, SPEC_LAYOUT)
    if block is None:
        return None, None
    for i in range(block.Count):
        ent = block.Item(i)
        if "table" in (ent.ObjectName or "").lower():
            return block, ent
    return block, None


def spec_cells(spec: dict) -> list[tuple[str, str, str, str]]:
    """Строки таблицы: заголовок, позиции, «Итого»."""
    rows = [SPEC_HEADER]
    for r in spec["rows"]:
        rows.append((r["article"], r["name"], str(r["qty"]),
                     _num(r["unit_weight"]) if r["unit_weight"] is not None else "—"))
    rows.append(("", "", "Итого, кг", _num(spec["total_weight"])))
    return rows


def spec_geometry(n_rows: int) -> dict:
    """Координаты линий таблицы: x столбцов и y строк (сверху вниз)."""
    top, row = spec_layout(n_rows)
    xs = [SPEC_LEFT]
    for w in SPEC_COLS:
        xs.append(round(xs[-1] + w, 3))
    ys = [round(top - k * row, 3) for k in range(n_rows + 1)]
    return {"xs": xs, "ys": ys, "row": row, "text": SPEC_TEXT[row]}


def _ensure_layer(doc, name: str) -> str | None:
    try:
        doc.Layers.Add(name)
        return name
    except Exception:
        return None


def _spec_table(doc, spec: dict) -> dict:
    block, table = _find_template_table(doc)
    if block is None:
        return {"ok": False, "reason": f"нет листа {SPEC_LAYOUT}"}
    hidden = False
    if table is not None:
        try:
            table.Visible = False      # таблицу СПДС шаблона не удаляем — скрываем
            hidden = True
        except Exception as exc:
            log.warning("Не удалось скрыть таблицу шаблона: %s", exc)

    cells = spec_cells(spec)
    g = spec_geometry(len(cells))
    xs, ys, h = g["xs"], g["ys"], g["text"]
    layer = _ensure_layer(doc, SPEC_LAYER)
    created = 0

    def put(ent):
        nonlocal created
        if layer:
            try:
                ent.Layer = layer
            except Exception:
                pass
        created += 1
        return ent

    # сетка: горизонтальные линии на всю ширину, вертикальные на всю высоту
    for y in ys:
        put(block.AddLine(_point(xs[0], y, 0), _point(xs[-1], y, 0)))
    for x in xs:
        put(block.AddLine(_point(x, ys[0], 0), _point(x, ys[-1], 0)))

    # текст: наименование — по левому краю, остальное — по центру
    for r, row in enumerate(cells):
        y_mid = (ys[r] + ys[r + 1]) / 2
        for c, text in enumerate(row):
            if not text:
                continue
            left = c == 1 and 0 < r < len(cells) - 1
            width = SPEC_COLS[c] - 2 * SPEC_PAD
            x = xs[c] + SPEC_PAD if left else (xs[c] + xs[c + 1]) / 2
            mt = put(block.AddMText(_point(x, y_mid, 0), width, text))
            mt.Height = h
            mt.AttachmentPoint = ATTACH_MIDDLE_LEFT if left else ATTACH_MIDDLE_CENTER
            mt.InsertionPoint = _point(x, y_mid, 0)
            try:
                mt.StyleName = "ГОСТ 2.304"
            except Exception:
                pass
    return {"ok": True, "rows": len(spec["rows"]), "row_height": g["row"],
            "top": ys[0], "template_table_hidden": hidden, "objects": created}


# --- лист A3: масштаб видов и размеры ---------------------------------------
SHEET_LAYOUT = "A3"
AC_PAPER_SPACE = 0
AC_MODEL_SPACE = 1


def _xyz(v) -> tuple[float, float, float]:
    v = tuple(float(c) for c in v)
    return v + (0.0,) * (3 - len(v))


def _sheet_viewports(block) -> list[tuple[object, dict]]:
    """Видовые экраны листа (без общего экрана самого листа)."""
    out = []
    for i in range(block.Count):
        ent = block.Item(i)
        if ent.ObjectName != "AcDbViewport":
            continue
        try:
            c = _xyz(ent.Center)
            w, h = float(ent.Width), float(ent.Height)
            if w > 300 or h > 250:          # общий экран листа
                continue
            out.append((ent, {"center": c[:2], "width": w, "height": h,
                              "direction": _xyz(ent.Direction), "target": _xyz(ent.Target)}))
        except Exception as exc:
            log.warning("Видовой экран %s не прочитан: %s", i, exc)
    return out


def _set_view(app, doc, vp, view) -> dict:
    """Центр и масштаб одного экрана. Возвращает фактические VIEWSIZE/масштаб для проверки."""
    res = {"scale": f"1:{view.scale}", "ok": False}
    try:
        vp.DisplayLocked = False
    except Exception:
        pass
    try:
        vp.ViewportOn = True
    except Exception:
        pass
    doc.MSpace = True
    doc.ActivePViewport = vp
    app.ZoomCenter(_point(*view.center_wcs), view.view_height)
    vp.CustomScale = 1.0 / view.scale
    try:
        size = float(doc.GetVariable("VIEWSIZE"))
        res["view_size"] = round(size, 1)
        res["actual_scale"] = f"1:{size / view.slot.height:.1f}"
    except Exception:
        pass
    doc.MSpace = False
    try:
        vp.DisplayLocked = True       # чтобы вид случайно не сдвинули — размеры на листе
    except Exception:
        pass
    res["ok"] = True
    return res


def _clear_sheet_dims(block) -> int:
    removed = 0
    for i in range(block.Count - 1, -1, -1):
        ent = block.Item(i)
        if "Dimension" in (ent.ObjectName or ""):
            ent.Delete()
            removed += 1
    return removed


def _add_dims(doc, block, dims) -> dict:
    layer = _ensure_layer(doc, views.DIM_LAYER)
    try:
        doc.ActiveDimStyle = doc.DimStyles.Item(views.DIM_STYLE)
    except Exception as exc:
        log.warning("Размерный стиль %s: %s", views.DIM_STYLE, exc)
    added, texts, failed = 0, 0, []
    for d in dims:
        ent = None
        try:
            if d.kind == "ordinate":
                # высотная отметка: ось Y (UseXAxis=False), горизонтальная выноска
                ent = block.AddDimOrdinate(_point(*d.p1, 0), _point(*d.line, 0), False)
            else:
                ent = block.AddDimRotated(_point(*d.p1, 0), _point(*d.p2, 0),
                                          _point(*d.line, 0), math.radians(d.rotation))
            ent.TextOverride = d.text
            added += 1
        except Exception as exc:
            failed.append(f"{d.view} {d.text}: {exc}")
            ent = None
            if d.kind == "ordinate":
                # запасной вариант — просто подпись у конца выноски
                try:
                    ent = block.AddMText(_point(d.line[0] + 1, d.line[1], 0), 15, d.text)
                    ent.Height = 2.5
                    ent.AttachmentPoint = ATTACH_MIDDLE_LEFT
                    ent.InsertionPoint = _point(d.line[0] + 1, d.line[1], 0)
                    texts += 1
                except Exception:
                    ent = None
        if ent is not None and layer:
            try:
                ent.Layer = layer
            except Exception:
                pass
    return {"dims": added, "texts": texts, "failed": failed}


def _setup_sheet(app, doc, elements: list[dict], parts: list[dict], origin) -> dict:
    """Масштаб и центр видов листа A3, затем размеры на листе."""
    layout = None
    for k in range(doc.Layouts.Count):
        if doc.Layouts.Item(k).Name == SHEET_LAYOUT:
            layout = doc.Layouts.Item(k)
    if layout is None:
        return {"ok": False, "reason": f"нет листа {SHEET_LAYOUT}"}
    block = layout.Block
    vps = _sheet_viewports(block)
    sheet = views.plan_sheet([v for _, v in vps], elements, parts, origin)

    doc.ActiveLayout = layout
    doc.ActiveSpace = AC_PAPER_SPACE
    done = {}
    for name, view in sheet["views"].items():
        vp = vps[view.slot.index][0]
        try:
            done[name] = _set_view(app, doc, vp, view)
        except Exception as exc:
            log.warning("Вид %s: %s", name, exc)
            done[name] = {"scale": f"1:{view.scale}", "ok": False, "reason": str(exc)}
            try:
                doc.MSpace = False
            except Exception:
                pass

    info = {"ok": all(v["ok"] for v in done.values()), "views": done,
            "found": sorted(sheet["slots"]), "old_dims_removed": _clear_sheet_dims(block)}
    info.update(_add_dims(doc, block, sheet["dims"]))
    return info


def _build(elements: list[dict], template: str, out_path: str, origin: list[float],
           extras: dict | None = None) -> dict:
    extras = extras or {}
    app = _get_or_start_app()
    doc = app.Documents.Open(template)
    # Сразу сохраняем под новым именем, чтобы не испортить шаблон
    doc.SaveAs(out_path)

    names = _block_names(doc)
    ms = _model_space(doc)

    # убрать пример конструкции из шаблона
    removed = 0
    for i in range(ms.Count - 1, -1, -1):
        ent = ms.Item(i)
        if ent.ObjectName == "AcDbBlockReference" and ARTICLE_RE.match(ent.Name or ""):
            ent.Delete()
            removed += 1

    ox, oy, oz = origin
    inserted, missing = 0, set()
    for e in elements:
        name = names.get(e["article"])
        if not name:
            missing.add(e["article"])
            continue
        ms.InsertBlock(_point(ox + e["x"], oy + e["y"], oz + e["z"]), name,
                       1.0, 1.0, 1.0, math.radians(e.get("rot", 0)))
        inserted += 1

    info = {"path": out_path, "inserted": inserted, "removed": removed,
            "missing": sorted(missing), "texts": 0, "table": False, "picture": False,
            "spec": None, "sheet": None}

    # основная надпись, таблица габаритов, ситуационный план
    if extras.get("fields"):
        info["texts"] = _replace_texts(doc, extras["fields"])
    if extras.get("area_rows"):
        try:
            info["table"] = _area_table(doc, extras["area_rows"], extras.get("area_text", ""))
        except Exception as exc:
            log.warning("Таблица габаритов: %s", exc)
    if extras.get("spec"):
        try:
            info["spec"] = _spec_table(doc, extras["spec"])
        except Exception as exc:
            log.warning("Спецификация: %s", exc)
            info["spec"] = {"ok": False, "reason": str(exc)}
    if extras.get("picture"):
        try:
            # как в ORG_V5: растр в модели в точке (200, 200), масштаб 200
            ms.AddRaster(extras["picture"], _point(200, 200, 0), 200, 0.0)
            info["picture"] = True
        except Exception as exc:
            log.warning("Ситуационный план: %s", exc)
    if extras.get("parts"):
        try:
            info["sheet"] = _setup_sheet(app, doc, elements, extras["parts"], origin)
        except Exception as exc:
            log.exception("Лист A3: виды и размеры")
            info["sheet"] = {"ok": False, "reason": str(exc)}
        try:
            doc.ActiveSpace = AC_MODEL_SPACE
        except Exception:
            pass

    try:
        app.ZoomExtents()
    except Exception:
        pass
    doc.Save()
    return info


def build(elements: list[dict], template: Path, out_path: Path, origin: list[float],
          extras: dict | None = None) -> dict:
    require_installed()
    if not template.exists():
        raise CadError("template_missing",
                       f"Не найден шаблон {template}. Укажите папку библиотеки в настройках.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        return _worker.call(_build, elements, str(template), str(out_path), origin, extras,
                            timeout=600)
    except CadError:
        raise
    except Exception as exc:
        log.exception("Ошибка nanoCAD")
        if is_gen_py_error(exc):
            raise gen_py_error() from exc
        raise CadError("nanocad_error", f"nanoCAD вернул ошибку: {exc}") from exc


# ------------------------------------------------------- показ и печать --
PRINT_LAYOUTS = ("A3", "A4")     # листы схемы в порядке печати
AC_MAX = 3                       # AcWindowState: 1 — обычное, 2 — свёрнуто, 3 — развёрнуто


def _same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _find_doc(app, path: str):
    docs = app.Documents
    for i in range(docs.Count):
        try:
            d = docs.Item(i)
            if _same_path(d.FullName, path):
                return d
        except Exception:
            continue
    return None


def _open_doc(app, path: str):
    doc = _find_doc(app, path) or app.Documents.Open(path)
    try:
        doc.Activate()
    except Exception:
        pass
    return doc


def _bring_to_front(app) -> None:
    """Показать окно nanoCAD поверх остальных (Windows не всегда разрешает — тогда мигает в панели задач)."""
    try:
        app.Visible = True
    except Exception:
        pass
    try:
        if app.WindowState == 2:
            app.WindowState = AC_MAX
    except Exception:
        pass
    try:
        import win32com.client
        import win32con
        import win32gui

        hwnd = int(app.HWND)
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        # нажатие Alt снимает запрет Windows на перевод фокуса в чужое окно
        win32com.client.Dispatch("WScript.Shell").SendKeys("%")
        win32gui.SetForegroundWindow(hwnd)
    except Exception as exc:
        log.info("Не удалось вывести окно nanoCAD на передний план: %s", exc)


def _show(path: str) -> dict:
    app = _get_or_start_app()
    _open_doc(app, path)
    _bring_to_front(app)
    return {"path": path, "shown": True}


def _paper_layouts(doc) -> list[str]:
    names = []
    for k in range(doc.Layouts.Count):
        lay = doc.Layouts.Item(k)
        try:
            if lay.ModelType:
                continue
        except Exception:
            if lay.Name in ("Model", "Модель"):
                continue
        names.append(lay.Name)
    return names


def is_file_device(name: str) -> bool:
    """PDF-принтер (встроенный PDF nanoCAD, Microsoft Print to PDF…): печатаем в файл,
    иначе nanoCAD открывает окно «Сохранить файл PDF как» и ждёт пользователя."""
    return "pdf" in (name or "").lower()


DWG_SUBDIR = "DWG"
PDF_SUBDIR = "PDF"


def pdf_name(dwg: str) -> str:
    """…/DWG/Схема.dwg -> …/PDF/Схема.pdf: все листы (A3, A4) в одном файле.

    DWG и PDF хранятся в двух подпапках папки вывода. Если чертёж лежит не в папке DWG
    (старые схемы, открытые вручную), PDF кладётся в подпапку PDF рядом с ним.
    """
    folder, file = os.path.split(dwg)
    stem = os.path.splitext(file)[0] + ".pdf"
    if os.path.basename(os.path.normpath(folder)).lower() == DWG_SUBDIR.lower():
        folder = os.path.dirname(os.path.normpath(folder))
    return os.path.join(folder, PDF_SUBDIR, stem)


def pdf_pages(path: str) -> int:
    """Число страниц PDF (pypdf; без него — грубый подсчёт по тексту файла)."""
    try:
        from pypdf import PdfReader

        return len(PdfReader(path).pages)
    except ImportError:
        data = Path(path).read_bytes()
        return len(re.findall(rb"/Type\s*/Page(?![s\w])", data))
    except Exception:
        return 0


def merge_pdfs(parts: list[str], target: str) -> bool:
    """Склеить PDF по порядку в target. False — нет pypdf (листы остаются отдельными файлами)."""
    try:
        from pypdf import PdfWriter
    except ImportError:
        log.warning("Нет пакета pypdf — PDF листов не склеены: pip install pypdf")
        return False
    writer = PdfWriter()
    for part in parts:
        writer.append(part)
    with open(target, "wb") as f:
        writer.write(f)
    return True


def _variant_list(value) -> list[str]:
    try:
        return [str(v) for v in (value or ()) if str(v).strip()]
    except TypeError:
        return []


def _pick_media(lay, layout_name: str) -> None:
    """После смены принтера подобрать формат бумаги по имени листа (A3/A4)."""
    try:
        lay.RefreshPlotDeviceInfo()
        media = _variant_list(lay.GetCanonicalMediaNames())
    except Exception:
        return
    key = layout_name.upper().replace(" ", "")
    for m in media:
        flat = m.upper().replace(" ", "").replace("_", "")
        if key in flat and "EXTRA" not in flat and "PLUS" not in flat:
            try:
                lay.CanonicalMediaName = m
            except Exception:
                pass
            return


def _use_printer(doc, name: str, printer: str):
    """Временно поставить листу принтер из настроек. Возвращает, как вернуть обратно."""
    lay = doc.Layouts.Item(name)
    old_device = lay.ConfigName
    if not printer or printer == old_device:
        return lay, old_device, None
    try:
        old_media = lay.CanonicalMediaName
    except Exception:
        old_media = None
    lay.ConfigName = printer
    _pick_media(lay, name)
    return lay, old_device, (old_device, old_media)


def _restore_printer(lay, restore) -> None:
    if not restore:
        return                      # лист шаблона в DWG не меняем
    old_device, old_media = restore
    try:
        lay.ConfigName = old_device
        if old_media:
            lay.CanonicalMediaName = old_media
    except Exception:
        pass


def _layouts_variant(names: list[str]):
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, tuple(names))


def _plot_pdf(doc, plot, names: list[str], target: str) -> dict:
    """Все листы в один PDF (подпапка PDF), без окна «Сохранить как».

    1) Все листы одной командой в один файл (многостраничный PDF, если nanoCAD умеет).
    2) Иначе — каждый лист во временный PDF и склейка (pypdf), временные файлы удаляются.
    """
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    if os.path.exists(target):
        os.remove(target)
    if len(names) > 1:
        try:
            plot.SetLayoutsToPlot(_layouts_variant(names))
            plot.PlotToFile(target)
            if os.path.exists(target) and pdf_pages(target) >= len(names):
                return {"pdf": target, "merged": True}
        except Exception as exc:
            log.info("Многостраничный PDF одной командой не получился: %s", exc)
        if os.path.exists(target):
            os.remove(target)
    base = os.path.splitext(target)[0]
    parts = []
    for name in names:
        part = f"{base}_{name}.pdf"
        if os.path.exists(part):
            os.remove(part)
        doc.ActiveLayout = doc.Layouts.Item(name)
        try:
            plot.SetLayoutsToPlot(_layouts_variant([name]))
        except Exception:
            pass
        plot.PlotToFile(part)
        parts.append(part)
    if len(parts) == 1:
        os.replace(parts[0], target)
        return {"pdf": target, "merged": True}
    if merge_pdfs(parts, target):
        for part in parts:
            try:
                os.remove(part)
            except OSError:
                pass
        return {"pdf": target, "merged": True}
    return {"pdf": parts[0], "parts": parts, "merged": False}


def _print(path: str, close: bool, printer: str = "") -> dict:
    """Печать листов A3 и A4: на принтер или (PDF-принтер) в один PDF в подпапке PDF.

    Не проверено на живом nanoCAD: Layout.ConfigName, Plot.PlotToDevice / PlotToFile — API, общий с AutoCAD.
    """
    app = _get_or_start_app()
    doc = _open_doc(app, path)
    layouts = _paper_layouts(doc)
    to_plot = [n for n in PRINT_LAYOUTS if n in layouts] or layouts
    if not to_plot:
        raise CadError("print_no_layouts", "В чертеже нет листов для печати.")
    try:
        doc.SetVariable("BACKGROUNDPLOT", 0)   # печатать сразу, а не в фоне — чтобы можно было закрыть файл
    except Exception:
        pass
    plot = doc.Plot
    switched = [_use_printer(doc, name, printer) for name in to_plot]
    try:
        device = printer or switched[0][1]
        result = {"path": path, "layouts": list(to_plot), "device": device, "pdf": [], "closed": False}
        if is_file_device(device):
            out = _plot_pdf(doc, plot, to_plot, pdf_name(path))
            result["pdf"] = out.get("parts") or [out["pdf"]]
            result["merged"] = out["merged"]
        else:
            for name in to_plot:
                doc.ActiveLayout = doc.Layouts.Item(name)
                plot.PlotToDevice()
    finally:
        for lay, _old, restore in switched:
            _restore_printer(lay, restore)
    if close:
        doc.Close(True)      # с сохранением
        result["closed"] = True
    return result


def _printers(template: str) -> dict:
    """Список принтеров nanoCAD и принтер листа A3 шаблона (шаблон открывается только на чтение)."""
    app = _get_or_start_app()
    opened = None
    try:
        doc = _find_doc(app, template)
        if doc is None:
            opened = doc = app.Documents.Open(template, True)
        lay = None
        for name in PRINT_LAYOUTS:
            try:
                lay = doc.Layouts.Item(name)
                break
            except Exception:
                continue
        lay = lay or doc.ActiveLayout
        try:
            lay.RefreshPlotDeviceInfo()
        except Exception:
            pass
        devices = [d for d in _variant_list(lay.GetPlotDeviceNames()) if d.lower() not in ("none", "нет")]
        return {"devices": devices, "template_device": lay.ConfigName}
    finally:
        if opened is not None:
            try:
                opened.Close(False)
            except Exception:
                pass


def _check_file(path: Path) -> None:
    require_installed()
    if not path.is_file():
        raise CadError("file_missing", f"Не найден файл схемы {path}. Постройте схему заново.")


def _call(fn, *args, timeout: float = 300):
    try:
        return _worker.call(fn, *args, timeout=timeout)
    except CadError:
        raise
    except Exception as exc:
        log.exception("Ошибка nanoCAD")
        if is_gen_py_error(exc):
            raise gen_py_error() from exc
        raise CadError("nanocad_error", f"nanoCAD вернул ошибку: {exc}") from exc


def show(path: Path) -> dict:
    _check_file(path)
    return _call(_show, str(path), timeout=60)


def print_file(path: Path, close: bool = False, printer: str = "") -> dict:
    _check_file(path)
    return _call(_print, str(path), close, printer)


def printers(template: Path) -> dict:
    require_installed()
    if not template.exists():
        raise CadError("template_missing", f"Не найден шаблон {template}. Укажите папку библиотеки в настройках.")
    return _call(_printers, str(template), timeout=120)
