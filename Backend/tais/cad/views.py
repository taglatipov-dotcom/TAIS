"""Виды листа A3: масштаб, центр вида и размеры — чистая геометрия, без nanoCAD.

Как устроен лист A3 шаблона (снято с Шаблон.dwg):
  * изометрия  — экран 100×135.4 мм, центр (70, 198.6),  направление (-1,-1,1);
  * вид спереди — экран 100×135.4 мм, центр (175, 198.6), направление (0,-1,0);
  * вид сбоку  — экран 100×135.4 мм, центр (280, 198.6), направление (1,0,0);
  * вид сверху — экран 100×72.2 мм,  центр (175, 75),    направление (0,0,1);
  * ситуационный план — экран 77×87.5 мм, смотрит на растр в модели (200…400, 200…400).

Видовой экран — ортогональная проекция. Если экран смотрит в направлении d,
центр вида — точка модели C, масштаб 1:N, то точка модели P попадает на лист в
    лист = центр_экрана + (proj(P) − proj(C)) / N,
где proj — координаты в системе вида (DCS): ось X = Z × d, ось Y = d × X
(так строит вид nanoCAD/AutoCAD; проверено по архивным схемам ORG_V5).
Поэтому положение любого узла на листе известно точно, и размеры ставятся
в пространстве листа: текст всегда 2.5 мм, на других видах их не видно.

Правила размеров — по ручным схемам архива ORG_V5:
  * вид спереди: общая длина каждой конструкции под ней;
  * вид сбоку: ширина под конструкцией, справа — высотные отметки ординатными размерами
    (ось Y): 0 у земли, настилы и верх стоек; подпись — отметка от первого узла
    (z − 105 мм), как в акте: 700, 2700 … 10200; близкие подписи разводятся изломом выноски;
  * план и изометрия без размеров.
  * несколько конструкций стоят друг за другом по Y (зазор 1 м): на виде спереди они
    перекрываются, поэтому разные длины уходят в следующий ряд (через 7 мм); на виде сбоку
    ширины в один ряд, отметки всех конструкций — одним общим столбцом.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..generator.model import BASE_LEVEL

# Ряд масштабов 1:N (знаменатели). ГОСТ 2.302 + распространённые 1:150, 1:250, 1:300.
# Масштаб на листе не подписывается, поэтому ряд можно сделать гуще.
SCALES = (50, 75, 100, 150, 200, 250, 300, 400, 500, 600, 800, 1000, 1500, 2000)
# Крупнее 1:50 не увеличиваем: маленькая башня иначе занимает весь экран
# (в ручных схемах самый крупный масштаб ~1:55). Чтобы разрешить крупнее — добавить 20, 25, 40 в начало.

# Поля внутри экрана, мм листа: (слева, справа, снизу, сверху).
# Снизу — место под горизонтальный размер, справа у бокового вида — под цепочку высот.
MARGINS = {
    "front": (3.0, 3.0, 13.0, 3.0),
    "side": (3.0, 21.0, 13.0, 3.0),
    "plan": (3.0, 3.0, 3.0, 3.0),
    "iso": (3.0, 3.0, 3.0, 3.0),
}
# Боковой вид берёт масштаб вида спереди (проекционная связь, общий уровень земли),
# если ширина конструкции на нём будет не меньше этого значения, мм; иначе — свой масштаб.
SIDE_MIN_WIDTH = 20.0
# Запас вокруг осей элементов (трубы, настилы, домкраты), мм модели
MODEL_PAD = 60.0

# Размеры (мм листа) — как в ручных схемах
DIM_OFFSET = 6.7         # от конструкции до размерной линии
ORD_LEADER = 8.0         # длина выноски ординатного размера (отметки) от конструкции
DIM_TEXT_STEP = 3.5      # минимальный шаг подписей отметок по высоте, чтобы не налезали
DIM_ROW_STEP = 7.0       # шаг между рядами горизонтальных размеров, если длины перекрываются

# Размещение нескольких конструкций на схеме
PART_GAP = 1000          # зазор между конструкциями, мм
DIM_STYLE = "СПДС"
DIM_LAYER = "TAIS_Размеры"

# Ситуационный план: растр в модели (точка вставки 200,200, масштаб 200)
PICTURE_BOX = (150.0, 150.0, 450.0, 450.0)

# Экраны листа A3 шаблона — для тестов и предпросмотра (в nanoCAD читаются из чертежа)
TEMPLATE_A3 = [
    {"center": (69.973, 198.577), "width": 100.0, "height": 135.409,
     "direction": (-1.0, -1.0, 1.0), "target": (2684.7, 2389.1, 3945.3)},
    {"center": (174.973, 198.577), "width": 100.0, "height": 135.409,
     "direction": (0.0, -1.0, 0.0), "target": (2336.5, 697.0, 2829.0)},
    {"center": (279.973, 198.577), "width": 100.0, "height": 135.409,
     "direction": (1.0, 0.0, 0.0), "target": (3301.9, 2563.1, 3001.5)},
    {"center": (174.973, 74.963), "width": 100.0, "height": 72.213,
     "direction": (0.0, 0.0, 1.0), "target": (3296.3, 1674.6, -161.8)},
    {"center": (375.322, 222.517), "width": 76.998, "height": 87.529,
     "direction": (0.0, 0.0, 1.0), "target": (271.1, 255.4, 0.0)},
]

Vec = tuple[float, float, float]


# ------------------------------------------------------------- векторы ----
def _norm(v: Vec) -> Vec:
    n = math.sqrt(sum(c * c for c in v))
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def basis(direction: Vec) -> tuple[Vec, Vec]:
    """Оси X и Y системы вида (DCS) для направления взгляда."""
    d = _norm(direction)
    if abs(d[0]) < 1e-9 and abs(d[1]) < 1e-9:      # вид сверху/снизу
        ex = (1.0, 0.0, 0.0)
    else:
        ex = _norm(_cross((0.0, 0.0, 1.0), d))
    ey = _norm(_cross(d, ex))
    return ex, ey


# ------------------------------------------------------------- экраны -----
@dataclass
class Slot:
    """Видовой экран листа."""
    name: str                       # iso / front / side / plan / picture
    center: tuple[float, float]     # центр экрана на листе, мм
    width: float
    height: float
    direction: Vec
    index: int = -1                 # номер экрана в списке, прочитанном из чертежа

    @property
    def axes(self) -> tuple[Vec, Vec]:
        return basis(self.direction)

    def project(self, p) -> tuple[float, float]:
        ex, ey = self.axes
        return _dot(p, ex), _dot(p, ey)


def classify(viewports: list[dict]) -> dict[str, Slot]:
    """Какой экран какой вид — по направлению взгляда.

    viewports: [{center, width, height, direction, target}] — как в TEMPLATE_A3.
    Экран сверху, который смотрит на растр ситуационного плана, — «picture»; его не трогаем.
    """
    slots: dict[str, Slot] = {}
    tops: list[tuple[int, dict]] = []
    for k, vp in enumerate(viewports):
        d = _norm(vp["direction"])
        name = None
        if abs(d[2]) > 0.999:
            tops.append((k, vp))
            continue
        if abs(d[2]) < 1e-6:
            if abs(d[1]) > 0.999:
                name = "front"
            elif abs(d[0]) > 0.999:
                name = "side"
        elif d[2] > 0:
            name = "iso"
        if name and name not in slots:
            slots[name] = Slot(name, tuple(vp["center"]), vp["width"], vp["height"], d, k)

    def on_picture(vp) -> bool:
        t = vp.get("target") or (0, 0, 0)
        x0, y0, x1, y1 = PICTURE_BOX
        return x0 <= t[0] <= x1 and y0 <= t[1] <= y1

    plans = [(k, vp) for k, vp in tops if not on_picture(vp)]
    pictures = [(k, vp) for k, vp in tops if on_picture(vp)]
    if not plans and len(tops) > 1:
        # запасной вариант: ситуационный план — самый правый экран
        tops.sort(key=lambda kv: kv[1]["center"][0])
        plans, pictures = tops[:-1], tops[-1:]
    if plans:
        k, vp = max(plans, key=lambda kv: kv[1]["width"] * kv[1]["height"])
        slots["plan"] = Slot("plan", tuple(vp["center"]), vp["width"], vp["height"],
                             _norm(vp["direction"]), k)
    for k, vp in pictures[:1]:
        slots["picture"] = Slot("picture", tuple(vp["center"]), vp["width"], vp["height"],
                                _norm(vp["direction"]), k)
    return slots


# ------------------------------------------------------------- габарит ----
def model_box(elements: list[dict], origin=(0.0, 0.0, 0.0), pad: float = MODEL_PAD):
    """Габарит модели (min, max) в координатах чертежа по точкам вставки, отрезкам и настилам."""
    ox, oy, oz = origin
    xs, ys, zs = [], [], []

    def add(x, y, z):
        xs.append(x)
        ys.append(y)
        zs.append(z)

    for e in elements:
        add(e["x"], e["y"], e["z"])
        for p in e.get("seg") or ():
            add(*p)
        if e.get("box"):
            bx, by, dx, dy = e["box"]
            add(bx + dx, by + dy, e["z"])
    if not xs:
        raise ValueError("Пустая модель — нечего показывать на видах")
    lo = (min(xs) + ox - pad, min(ys) + oy - pad, min(min(zs), 0.0) + oz)
    hi = (max(xs) + ox + pad, max(ys) + oy + pad, max(zs) + oz + pad)
    return lo, hi


def _corners(lo: Vec, hi: Vec) -> list[Vec]:
    return [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def _extent(slot: Slot, lo: Vec, hi: Vec) -> tuple[float, float, float, float]:
    """Габарит модели в системе вида: (u_min, v_min, u_max, v_max), мм модели."""
    pts = [slot.project(c) for c in _corners(lo, hi)]
    us = [p[0] for p in pts]
    vs = [p[1] for p in pts]
    return min(us), min(vs), max(us), max(vs)


def _usable(slot: Slot, extra=(0.0, 0.0, 0.0, 0.0)) -> tuple[float, float, float, float]:
    """Рабочая область экрана на листе с учётом полей: (x0, y0, x1, y1).
    extra — добавка к полям (слева, справа, снизу, сверху) под дополнительные ряды размеров."""
    left, right, bottom, top = (m + e for m, e in zip(MARGINS.get(slot.name, (3.0, 3.0, 3.0, 3.0)), extra))
    cx, cy = slot.center
    return (cx - slot.width / 2 + left, cy - slot.height / 2 + bottom,
            cx + slot.width / 2 - right, cy + slot.height / 2 - top)


def fit_scale(span_u: float, span_v: float, avail_w: float, avail_h: float,
              scales=SCALES) -> int:
    """Самый крупный масштаб из ряда, при котором габарит влезает в область."""
    for n in scales:
        if span_u / n <= avail_w + 1e-9 and span_v / n <= avail_h + 1e-9:
            return n
    # не влезло даже в самый мелкий — берём ближайший круглый
    need = max(span_u / max(avail_w, 1e-6), span_v / max(avail_h, 1e-6))
    return int(math.ceil(need / 100.0) * 100)


@dataclass
class View:
    """Настроенный вид: экран, масштаб 1:scale и точка модели в центре экрана."""
    slot: Slot
    scale: int
    center_uv: tuple[float, float]          # проекция центральной точки, мм модели
    extent: tuple[float, float, float, float] = field(default=(0, 0, 0, 0))

    @property
    def center_wcs(self) -> Vec:
        """Точка модели, которая окажется в центре экрана (для ZoomCenter)."""
        ex, ey = self.slot.axes
        u, v = self.center_uv
        return (ex[0] * u + ey[0] * v, ex[1] * u + ey[1] * v, ex[2] * u + ey[2] * v)

    @property
    def view_height(self) -> float:
        """Высота вида в мм модели при заданном масштабе (VIEWSIZE)."""
        return self.slot.height * self.scale

    def to_paper(self, p) -> tuple[float, float]:
        u, v = self.slot.project(p)
        cx, cy = self.slot.center
        return (cx + (u - self.center_uv[0]) / self.scale,
                cy + (v - self.center_uv[1]) / self.scale)


def _place(slot: Slot, scale: int, ext, extra=(0.0, 0.0, 0.0, 0.0)) -> View:
    """Разместить габарит по центру рабочей области экрана."""
    x0, y0, x1, y1 = _usable(slot, extra)
    cx, cy = slot.center
    # центр рабочей области смещён от центра экрана из-за несимметричных полей
    du = ((x0 + x1) / 2 - cx) * scale
    dv = ((y0 + y1) / 2 - cy) * scale
    mid_u = (ext[0] + ext[2]) / 2
    mid_v = (ext[1] + ext[3]) / 2
    return View(slot, scale, (mid_u - du, mid_v - dv), ext)


def layout_views(slots: dict[str, Slot], lo: Vec, hi: Vec, scales=SCALES,
                 extra: dict[str, tuple] | None = None) -> dict[str, View]:
    """Масштаб и центр для изометрии, вида спереди, сбоку и сверху.

    Вид спереди и план — общий масштаб (план под фасадом в проекционной связи).
    Вид сбоку — масштаб фасада, если конструкция на нём не слишком узкая, иначе свой.
    Изометрия — свой масштаб.
    extra — добавочные поля экранов под лишние ряды размеров: {имя: (слева, справа, снизу, сверху)}.
    """
    extra = extra or {}
    zero = (0.0, 0.0, 0.0, 0.0)
    exts = {n: _extent(s, lo, hi) for n, s in slots.items() if n != "picture"}

    def need(name: str) -> int:
        s, e = slots[name], exts[name]
        x0, y0, x1, y1 = _usable(s, extra.get(name, zero))
        return fit_scale(e[2] - e[0], e[3] - e[1], x1 - x0, y1 - y0, scales)

    views: dict[str, View] = {}
    common = max((need(n) for n in ("front", "plan") if n in slots), default=None)
    for n in ("front", "plan"):
        if n in slots:
            views[n] = _place(slots[n], common, exts[n], extra.get(n, zero))
    if "side" in slots:
        own = need("side")
        sc = own
        if common is not None and common >= own:
            e = exts["side"]
            if (e[2] - e[0]) / common >= SIDE_MIN_WIDTH:
                sc = common
        views["side"] = _place(slots["side"], sc, exts["side"], extra.get("side", zero))
    if "iso" in slots:
        views["iso"] = _place(slots["iso"], need("iso"), exts["iso"], extra.get("iso", zero))
    return views


# ------------------------------------------------------- части схемы -----
def _part_box(part: dict) -> tuple[float, float, float, float]:
    """Габарит части схемы в плане (x0, y0, x1, y1), мм модели, с учётом сдвига."""
    g = part["grid"]
    dx, dy = part.get("offset", 0), part.get("offset_y", 0)
    return g["xs"][0] + dx, g["ys"][0] + dy, g["xs"][-1] + dx, g["ys"][-1] + dy


def _stack(intervals: list[tuple[float, float]]) -> list[int]:
    """Номер ряда для каждого отрезка: перекрывающиеся отрезки — в разные ряды.
    Одинаковые отрезки — в один ряд (это один и тот же размер)."""
    rows: list[list[tuple[float, float]]] = []
    out = []
    for a, b in intervals:
        for k, row in enumerate(rows):
            if (a, b) in row or all(b <= c + 1e-6 or a >= d - 1e-6 for c, d in row):
                if (a, b) not in row:
                    row.append((a, b))
                out.append(k)
                break
        else:
            rows.append([(a, b)])
            out.append(len(rows) - 1)
    return out


def dim_extra(parts: list[dict]) -> dict[str, tuple]:
    """Добавочные поля под размеры, которые не влезают в один ряд/одну цепочку."""
    if not parts:
        return {}
    boxes = [_part_box(p) for p in parts]
    front_rows = max(_stack([(b[0], b[2]) for b in boxes])) + 1
    side_rows = max(_stack([(b[1], b[3]) for b in boxes])) + 1
    return {
        "front": (0.0, 0.0, (front_rows - 1) * DIM_ROW_STEP, 0.0),
        "side": (0.0, 0.0, (side_rows - 1) * DIM_ROW_STEP, 0.0),
    }


# ------------------------------------------------------- размещение ------
def arrange(parts: list[dict], gap: float = PART_GAP) -> list[tuple[float, float]]:
    """Конструкции схемы — друг за другом по Y с зазором gap, выровнены по началу X.
    parts: [{grid: {xs, ys}}]. Возвращает [(dx, dy)] — сдвиг каждой части."""
    offs, y = [], 0.0
    for p in parts:
        g = p["grid"]
        offs.append((-float(g["xs"][0]), y - g["ys"][0]))
        y += (g["ys"][-1] - g["ys"][0]) + gap
    return offs


# ------------------------------------------------------------- размеры ----
@dataclass
class Dim:
    """Размер на листе.

    kind="rotated": p1, p2 — выносные точки, line — точка на размерной линии, rotation — угол.
    kind="ordinate": p1 — точка отметки (у конструкции), line — конец выноски, подпись за ним;
    ось Y (горизонтальная выноска). p2 = p1.
    """
    p1: tuple[float, float]
    p2: tuple[float, float]
    line: tuple[float, float]
    rotation: float                 # для rotated: 0 — горизонтальный, 90 — вертикальный
    text: str
    kind: str = "rotated"
    view: str = ""

    def to_dict(self) -> dict:
        return {"kind": self.kind, "p1": self.p1, "p2": self.p2, "line": self.line,
                "rotation": self.rotation, "text": self.text, "view": self.view}


def _r(p) -> tuple[float, float]:
    return (round(p[0], 3), round(p[1], 3))


def level_label(z: float) -> str:
    """Подпись отметки: высота от первого узла (как в акте), у земли — 0."""
    return "0" if z <= 0 else f"{round(z - BASE_LEVEL):d}"


def _spread(ys: list[float], step: float) -> list[float]:
    """Подписи по высоте не ближе step друг к другу: раздвигаем вверх, не трогая нижнюю."""
    out: list[float] = []
    for y in ys:
        out.append(y if not out or y - out[-1] >= step else out[-1] + step)
    return out


def _horizontal(view: View, spans: list[tuple]) -> list[Dim]:
    """Горизонтальные размеры под видом: spans = [(точка1, точка2, текст)] в модели.
    Перекрывающиеся — в разные ряды, одинаковые — один раз."""
    pts = [(view.to_paper(a), view.to_paper(b), t) for a, b, t in spans]
    ground = min(min(a[1], b[1]) for a, b, _ in pts)
    rows = _stack([(round(min(a[0], b[0]), 3), round(max(a[0], b[0]), 3)) for a, b, _ in pts])
    out, seen = [], set()
    for (a, b, text), k in zip(pts, rows):
        a, b = (a, b) if a[0] <= b[0] else (b, a)
        key = (round(a[0], 2), round(b[0], 2), text)
        if key in seen:
            continue
        seen.add(key)
        y = ground - DIM_OFFSET - k * DIM_ROW_STEP
        out.append(Dim(_r(a), _r(b), _r((b[0], y)), 0.0, text, view=view.slot.name))
    return out


def plan_dims(views: dict[str, View], parts: list[dict], origin=(0.0, 0.0, 0.0)) -> list[Dim]:
    """Размеры на листе по частям схемы.

    parts: [{offset, offset_y, grid: {xs, ys, decks, top}}] — как в run_scheme.
    """
    ox, oy, oz = origin
    dims: list[Dim] = []
    if not parts:
        return dims
    boxes = [_part_box(p) for p in parts]

    front = views.get("front")
    if front:
        spans = [((b[0] + ox, b[1] + oy, oz), (b[2] + ox, b[1] + oy, oz), f"{round(b[2] - b[0]):d}")
                 for b in boxes]
        dims.extend(_horizontal(front, spans))

    side = views.get("side")
    if side:
        spans = [((b[2] + ox, b[1] + oy, oz), (b[2] + ox, b[3] + oy, oz), f"{round(b[3] - b[1]):d}")
                 for b in boxes]
        dims.extend(_horizontal(side, spans))

        # высотные отметки справа (ординатные размеры): 0, настилы и верх всех конструкций
        levels = sorted({0.0, *(float(p["grid"]["top"]) for p in parts),
                         *(float(z) for p in parts for z in p["grid"].get("decks", ()))})
        edge = max(side.to_paper((ox, b[3] + oy, oz))[0] for b in boxes)
        ys = [side.to_paper((ox, oy, z + oz))[1] for z in levels]
        text_ys = _spread(ys, DIM_TEXT_STEP)
        for z, y, ty in zip(levels, ys, text_ys):
            dims.append(Dim(_r((edge, y)), _r((edge, y)), _r((edge + ORD_LEADER, ty)), 0.0,
                            level_label(z), kind="ordinate", view="side"))
    return dims


# ------------------------------------------------------------- всё вместе -
def plan_sheet(viewports: list[dict], elements: list[dict], parts: list[dict],
               origin=(0.0, 0.0, 0.0)) -> dict:
    """Полный расчёт листа: какие экраны, масштабы, центры видов и размеры."""
    slots = classify(viewports)
    lo, hi = model_box(elements, origin)
    views = layout_views(slots, lo, hi, extra=dim_extra(parts))
    dims = plan_dims(views, parts, origin)
    return {"slots": slots, "views": views, "dims": dims, "box": (lo, hi)}


def summary(sheet: dict) -> dict:
    """Короткий отчёт для ответа API и журнала."""
    return {
        "views": {n: {"scale": f"1:{v.scale}", "center": [round(c, 1) for c in v.center_wcs]}
                  for n, v in sheet["views"].items()},
        "dims": len(sheet["dims"]),
    }
