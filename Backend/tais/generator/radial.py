"""Радиальные леса — замкнутое кольцо вокруг объекта (резервуар, колонна и т.п.).

Как строится:
  1. Длина по акту — сумма длин всех ячеек (по внутренней стороне кольца). Подбираем,
     из каких ячеек её набрать (choose_cells): одинаковые ячейки одного типоразмера или,
     если длина на них не делится, обычная разбивка split_length.
  2. Из ячеек собирается прямая фасадная «лента» в одну ячейку шириной (с уширением наружу,
     если оно включено) и раскладывается обычными правилами rules.generate — стойки, ригели,
     настилы, люки, перила, бортики, диагонали как у фасадных лесов.
  3. Ленту «сгибаем» в кольцо: каждая ячейка поворачивается вокруг своей внутренней стойки.
     Внутренние стойки соседних ячеек общие (внутренняя сторона — многоугольник, вписанный
     в окружность радиуса R), наружные стойки расходятся — между ними ставится ригель-вставка
     стандартной длины на каждой отметке наружных ригелей (и бортик по верхнему настилу).
  4. Кольцо замкнуто: торцы ленты становятся обычным внутренним стыком (между последней
     и первой ячейкой), их наружная обшивка и диагонали снимаются.

Соглашения локальной ленты: X — вдоль кольца, Y = 0 — наружная сторона (там вход и люк),
наибольший Y — внутренняя сторона (к объекту). Ячейка 0 (с люком и входом) — спереди,
с наименьшим Y на схеме, без поворота.

Ограничение: при общих внутренних стойках наружный зазор равен 2·d·sin(φ/2) (d — расстояние
от внутренней стороны, φ — угол поворота) и в общем случае не равен длине стандартного ригеля.
Ячейки подбираются так, чтобы разница была наименьшей; остаток выдаётся предупреждением.
"""
from __future__ import annotations

import math
from dataclasses import replace
from itertools import combinations

from . import catalog
from .bays import BAY_SIZES, SplitError, cumulative, split_length
from .constructions import ConstructionInput, build_group, to_mm
from .model import Element, widening_levels
from .rules import ART_LEDGER, ART_TOEBOARD, generate

MIN_CELLS = 4            # меньше 4 ячеек кольцо не собрать
DEV_MAX = 50             # мм: допустимая разница между наружным зазором и ригелем-вставкой
HOLE_OK = 150            # мм: щель в настиле у стоек, которую не выносим в предупреждение
SAG_MAX = 300            # мм: прогиб прямого участка — насколько его середина ближе к объекту, чем стыки
EPS = 1e-6
LEDGER_SIZES = tuple(sorted(int(a.split(".")[1]) for a in catalog.CATALOG if a.startswith("S11013.")))


# ------------------------------------------------------------ геометрия ---
def ring_radius(cells: list[int]) -> float:
    """Радиус окружности, в которую вписан многоугольник из внутренних сторон ячеек."""
    lmax = max(cells)

    def excess(r: float) -> float:
        return sum(2 * math.asin(min(1.0, c / (2 * r))) for c in cells) - 2 * math.pi

    lo, hi = lmax / 2, float(sum(cells))
    if excess(lo) < 0:
        raise SplitError("Радиальные леса: ячейки слишком разной длины — кольцо не замыкается")
    for _ in range(60):
        mid = (lo + hi) / 2
        if excess(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def central_angles(cells: list[int], r: float) -> list[float]:
    return [2 * math.asin(min(1.0, c / (2 * r))) for c in cells]


def joint_angles(cells: list[int], r: float) -> list[float]:
    """Угол поворота в стыке k (между ячейками k−1 и k), радианы."""
    a = central_angles(cells, r)
    return [(a[k - 1] + a[k]) / 2 for k in range(len(cells))]


def nearest_ledger(gap: float) -> int:
    return min(LEDGER_SIZES, key=lambda s: (abs(s - gap), s))


def gap_table(sections: list[int], offsets: list[int]) -> list[tuple[int, int, float, int]]:
    """[(стык, расстояние от внутренней стороны, зазор, ригель-вставка)]."""
    r = ring_radius(sections)
    return [(k, d, 2 * d * math.sin(phi / 2), nearest_ledger(2 * d * math.sin(phi / 2)))
            for k, phi in enumerate(joint_angles(sections, r)) for d in offsets]


def group(cells: list[int], k: int) -> list[int]:
    """Длины прямых участков: по k ячеек подряд."""
    return [sum(cells[i:i + k]) for i in range(0, len(cells), k)]


def sagitta(sections: list[int]) -> float:
    """Прогиб самого длинного прямого участка относительно окружности, мм."""
    r = ring_radius(sections)
    return r * (1 - math.cos(max(central_angles(sections, r)) / 2))


def _score(cells: list[int], offsets: list[int]) -> list[tuple[tuple, list[int], int]]:
    """Варианты поворота: каждые k ячеек (k — делитель числа ячеек, участков не меньше 4).

    Вариант годный, если разница зазора и ригеля-вставки ≤ DEV_MAX и прогиб участка ≤ SAG_MAX.
    Среди годных: один типоразмер, крупнее ячейки, поворот чаще, меньше разница.
    Если годных нет — наименьшая разница (с допустимым прогибом, если такой есть)."""
    out = []
    n = len(cells)
    for k in range(1, n // MIN_CELLS + 1):
        if n % k:
            continue
        sections = group(cells, k)
        try:
            dev = max(abs(g - s) for _, _, g, s in gap_table(sections, offsets))
            sag = sagitta(sections)
        except SplitError:
            continue
        if dev <= DEV_MAX and sag <= SAG_MAX:
            key = (0, len(set(cells)) != 1, -min(cells), k, dev)
        else:
            key = (1, sag > SAG_MAX, dev, k)
        out.append((key, cells, k))
    return out


def choose_cells(length: int, offsets: list[int]) -> tuple[list[int], int]:
    """Из каких ячеек набрать длину кольца и через сколько ячеек поворачивать.

    Ячейки: одинаковые одного типоразмера (если длина делится); если годного варианта нет —
    ещё наборы из двух типоразмеров (перемешаны равномерно по кольцу) и обычная разбивка
    split_length. Поворот — в каждом стыке или через k ячеек (прямые участки): на большом
    кольце зазор у одной ячейки меньше самого короткого ригеля (0.25 м). Оценка — _score.
    """
    scored = []
    for s in BAY_SIZES:
        if length % s == 0 and length // s >= MIN_CELLS:
            scored += _score([s] * (length // s), offsets)
    if not scored or min(scored)[0][0] != 0:
        cands: list[list[int]] = []
        for a, b in combinations(BAY_SIZES, 2):
            for ca in range(1, length // a + 1):
                rest = length - ca * a
                if rest > 0 and rest % b == 0 and ca + rest // b >= MIN_CELLS:
                    cands.append(_interleave(a, ca, b, rest // b))
        try:
            mixed = split_length(length)
            if len(mixed) >= MIN_CELLS and mixed not in cands:
                cands.append(mixed)
        except SplitError:
            pass
        for c in cands:
            scored += _score(c, offsets)
    if not scored:
        raise SplitError(
            f"Радиальные леса: длину {length / 1000:g} м нельзя набрать хотя бы из {MIN_CELLS} ячеек "
            f"{', '.join(f'{s / 1000:g}' for s in BAY_SIZES)} м")
    _, cells, k = min(scored, key=lambda t: t[0])
    return cells, k


def _interleave(a: int, ca: int, b: int, cb: int) -> list[int]:
    """Две группы ячеек, равномерно перемешанные по кольцу (как алгоритм Брезенхэма)."""
    out, acc = [], 0
    for _ in range(ca + cb):
        acc += ca
        if acc >= ca + cb:
            acc -= ca + cb
            out.append(a)
        else:
            out.append(b)
    return out


# --------------------------------------------------------- сгибание ленты -
class Ring:
    """Положение участков кольца: участок k (одна или несколько ячеек подряд, прямой) —
    от внутренней стойки P[k] до P[k+1]; xs — границы участков на ленте."""

    def __init__(self, cells: list[int], xs: list[int], y_in: float):
        self.cells, self.xs, self.y_in = cells, xs, y_in
        self.n = len(cells)
        self.r = ring_radius(cells)
        alpha = central_angles(cells, self.r)
        b = -math.pi / 2 - alpha[0] / 2          # ячейка 0 — спереди (наименьший Y)
        self.p = []
        for k in range(self.n):
            self.p.append((self.r * math.cos(b), self.r * math.sin(b)))
            b += alpha[k]
        self.p.append(self.p[0])
        self.u = []
        for k, c in enumerate(cells):
            (x0, y0), (x1, y1) = self.p[k], self.p[k + 1]
            self.u.append(((x1 - x0) / c, (y1 - y0) / c))
        self.turn = joint_angles(cells, self.r)

    def angle(self, k: int) -> float:
        ux, uy = self.u[k]
        return math.degrees(math.atan2(uy, ux))

    def tf(self, k: int, x: float, y: float) -> tuple[float, float]:
        """Точка локальной ленты (x, y) ячейки k → план кольца.
        Наружная нормаль n = (uy, −ux): кольцо обходится против часовой стрелки."""
        px, py = self.p[k]
        ux, uy = self.u[k]
        a, d = x - self.xs[k], self.y_in - y
        return px + a * ux + d * uy, py + a * uy - d * ux

    def move(self, e: Element, k: int) -> Element:
        x, y = self.tf(k, e.x, e.y)
        seg = [[*self.tf(k, p[0], p[1]), p[2]] for p in e.seg] if e.seg else None
        box = poly = None
        if e.box:
            bx, by, dx, dy = e.box
            poly = [list(self.tf(k, cx, cy))
                    for cx, cy in ((bx, by), (bx + dx, by), (bx + dx, by + dy), (bx, by + dy))]
            px = [p[0] for p in poly]
            py = [p[1] for p in poly]
            box = (min(px), min(py), max(px) - min(px), max(py) - min(py))
        rot = round((e.rot + self.angle(k)) % 360, 6)
        return Element(e.article, x, y, e.z, rot, e.kind, seg, box, poly)


def _line(e: Element) -> tuple[float, str]:
    """Положение элемента вдоль ленты: (x, тип) — "x" элемент вдоль X или внутри ячейки,
    "y" элемент вдоль Y (на линии стоек), "point" — в узле (стойка, домкрат…)."""
    if e.seg:
        (x0, y0, _), (x1, y1, _) = e.seg
        if abs(x0 - x1) > EPS:
            return (x0 + x1) / 2, "x"
        if abs(y0 - y1) > EPS:
            return x0, "y"
        return x0, "point"
    if e.box:
        return e.box[0] + e.box[2] / 2, "x"
    return e.x, "point"


def _owners(ring: Ring, e: Element) -> list[int]:
    """Каким ячейкам принадлежит элемент ленты. Внутренние стойки стыка — общие,
    наружные стойки и ригели поперёк ленты на стыке — у каждой из двух ячеек свои.
    Торцы ленты (x = 0 и x = L) — стык последней и первой ячейки."""
    xs, n = ring.xs, ring.n
    rx, kind = _line(e)
    for k in range(n):
        if xs[k] + EPS < rx < xs[k + 1] - EPS:
            return [k]
    j = min(range(n + 1), key=lambda k: abs(xs[k] - rx))
    if kind == "x":
        return [min(j, n - 1)]
    if kind == "y":
        return [] if j in (0, n) else [j - 1, j]   # торцы ленты собираются заново
    inner = abs(e.y - ring.y_in) < EPS
    if j == n:
        return [] if inner else [n - 1]             # внутренняя стойка = стойка ячейки 0
    if j == 0:
        return [0]
    return [j] if inner else [j - 1, j]


def bend(st, elements: list[Element], k: int, deck_width: int | None = None
         ) -> tuple[list[Element], list[dict], Ring]:
    """Согнуть ленту: поворот через каждые k ячеек (на границах прямых участков).
    deck_width — ширина настила (основной части без уширения), для планок в клиньях."""
    xs = st.xs[::k]
    ring = Ring([b - a for a, b in zip(xs, xs[1:])], xs, st.ys[-1])
    n = ring.n
    local: list[tuple[int, Element]] = []
    for e in elements:
        for k in _owners(ring, e):
            local.append((k, e))
    # стык последней и первой ячейки — как любой внутренний стык: ригели поперёк ленты
    # берём с первого внутреннего стыка
    for e in elements:
        rx, kind = _line(e)
        if kind == "y" and e.kind == "ledger" and abs(rx - xs[1]) < EPS:
            for k, x in ((0, xs[0]), (n - 1, xs[n])):
                local.append((k, replace(e, x=x, seg=[[x, p[1], p[2]] for p in e.seg])))

    # отметки наружных ригелей и бортиков по линиям Y каждой ячейки
    levels: dict[tuple[str, int, float], set[float]] = {}
    for k, e in local:
        if e.kind in ("ledger", "toeboard") and _line(e)[1] == "x":
            levels.setdefault((e.kind, k, round(e.seg[0][1], 3)), set()).add(e.z)

    out = [ring.move(e, k) for k, e in local]
    gaps: list[dict] = []
    for j in range(n):
        prev = (j - 1) % n
        for yl in st.ys[:-1]:
            ax, ay = ring.tf(prev, xs[prev + 1], yl)
            bx, by = ring.tf(j, xs[j], yl)
            gap = math.hypot(bx - ax, by - ay)
            if gap < 1:
                continue
            size = nearest_ledger(gap)
            dx, dy = (bx - ax) / gap, (by - ay) / gap
            sx, sy = ax + dx * (gap - size) / 2, ay + dy * (gap - size) / 2   # вставка по центру
            rot = round(math.degrees(math.atan2(dy, dx)) % 360, 6)
            gaps.append({"joint": j, "offset": round(st.ys[-1] - yl), "gap": round(gap),
                         "ledger": size, "dev": round(gap - size)})
            key = round(yl, 3)
            for kind, fmt in (("ledger", ART_LEDGER), ("toeboard", ART_TOEBOARD)):
                zs = levels.get((kind, prev, key), set()) | levels.get((kind, j, key), set())
                for z in sorted(zs):
                    out.append(Element(fmt.format(size), sx, sy, z, rot, kind=kind,
                                       seg=[[sx, sy, z], [sx + dx * size, sy + dy * size, z]]))
    if deck_width:
        _wedge_planks(st, ring, local, deck_width, out, gaps)
    return out, gaps, ring


# ------------------------------------------------- планки в клиньях ------
PLANK_WIDTH = 250
PLANK_SIZES = tuple(sorted(int(a.split(".")[1]) for a in catalog.CATALOG if a.startswith("U00141.")))
ART_PLANK_GAP = "U00141.{:04d}"   # планка стальная 0.25 м — перекрытие клина между ячейками
PLANK_BEARING = 100               # мм: планка заходит на настил каждой ячейки не меньше чем на столько
POST_CLEAR = 60                   # мм: от оси стойки до края планки (труба + розетка)


def _wedge_planks(st, ring: Ring, local, deck_width: int, out: list[Element], gaps: list[dict]) -> None:
    """Планки поперёк клина между соседними ячейками на каждом настиле — чтобы можно было ходить.

    Клин — треугольник: вершина у общей внутренней стойки P, основание — наружный зазор.
    Ось s — по биссектрисе от P наружу, t — поперёк. Ширина клина на расстоянии s: 2·s·tg(φ/2).
    Планки 0.25 м кладутся поперёк (вдоль t) полосами от наружного края к стойке P; длина —
    ширина клина у наружного края полосы плюс заход на настил с обеих сторон, ближайшая из
    1.0/1.5/2.0/2.5 м. Ограничения: не ближе POST_CLEAR к стойкам (P и расходящимся стойкам
    линий внутри настила), концы планки не выходят за наружный и внутренний край настила.
    Что не перекрыто (у внутренней стойки, у стоек) — в gaps[...]["hole"] для предупреждения.
    """
    y_in = st.ys[-1]
    lines = sorted(y_in - y for y in st.ys if 0 < y_in - y <= deck_width)   # линии стоек настила
    n = ring.n
    decks: dict[int, set[float]] = {}
    for k, e in local:
        if e.kind in ("deck", "hatch") and e.box:
            decks.setdefault(k, set()).add(e.z)
    holes: dict[int, float] = {}
    for j in range(n):
        prev = (j - 1) % n
        zs = sorted(decks.get(prev, set()) & decks.get(j, set()))
        if not zs:
            continue
        half = ring.turn[j] / 2
        tg = math.tan(half)
        # биссектриса: сумма наружных нормалей соседних участков
        (ux0, uy0), (ux1, uy1) = ring.u[prev], ring.u[j]
        mx, my = uy0 + uy1, -ux0 - ux1
        norm = math.hypot(mx, my)
        mx, my = mx / norm, my / norm
        tx, ty = my, -mx                     # поперёк клина; локальная Y блока = +90° от t = m
        rot = round(math.degrees(math.atan2(ty, tx)) % 360, 6)
        px, py = ring.p[j]
        bands, hole = _plan_bands([d * math.cos(half) for d in lines], tg)
        holes[j] = hole
        for s0, size in bands:
            # угол полосы с меньшими локальными X, Y: s0 по биссектрисе, −L/2 поперёк
            cx, cy = px + mx * s0 - tx * size / 2, py + my * s0 - ty * size / 2
            corners = [(cx, cy), (cx + tx * size, cy + ty * size),
                       (cx + tx * size + mx * PLANK_WIDTH, cy + ty * size + my * PLANK_WIDTH),
                       (cx + mx * PLANK_WIDTH, cy + my * PLANK_WIDTH)]
            xs_ = [c[0] for c in corners]
            ys_ = [c[1] for c in corners]
            box = (min(xs_), min(ys_), max(xs_) - min(xs_), max(ys_) - min(ys_))
            for z in zs:
                out.append(Element(ART_PLANK_GAP.format(size), cx, cy, z, rot, kind="deck",
                                   box=box, poly=[list(c) for c in corners]))
    for g in gaps:
        g["hole"] = round(holes.get(g["joint"], 0))


def _plan_bands(lines_s: list[float], tg: float) -> tuple[list[tuple[float, int]], float]:
    """Полосы планок в клине: [(s нижнего края, длина планки)] и ширина самой широкой
    неперекрытой щели, мм. lines_s — положение линий стоек по биссектрисе (последняя — наружный край)."""
    bands: list[tuple[float, int]] = []
    hole = 0.0
    s_out = lines_s[-1]
    obstacles = [0.0] + lines_s               # стойка P и расходящиеся стойки
    for k in range(len(obstacles) - 1, 0, -1):
        lo, hi = obstacles[k - 1], obstacles[k]
        top = hi - POST_CLEAR
        bottom_limit = lo + POST_CLEAR
        while True:
            need = 2 * top * tg + 2 * PLANK_BEARING
            size = next((p for p in PLANK_SIZES if p >= need), None)
            if size is None:
                hole = max(hole, 2 * top * tg)
                break
            if hi == s_out:
                # конец планки не должен выходить за наружный край настила
                # (опускаем полосу; длина от этого только уменьшается — проверка сходится)
                over = (size / 2 - s_out * tg) * tg
                if over > s_out - top + 0.5:
                    top = s_out - over
                    continue
            bottom = top - PLANK_WIDTH
            # и за внутренний край настила (у стойки P край расходится под углом φ/2)
            if bottom < bottom_limit or (lo == 0.0 and bottom < size / 2 * tg):
                hole = max(hole, 2 * top * tg)
                break
            bands.append((bottom, size))
            top = bottom
    return bands, hole


def _normalize(elements: list[Element]) -> tuple[float, float]:
    """Сдвинуть кольцо так, чтобы габарит в плане начинался с (0, 0); вернуть размеры габарита."""
    pts = []
    for e in elements:
        pts.append((e.x, e.y))
        pts.extend((p[0], p[1]) for p in e.seg or ())
        pts.extend((p[0], p[1]) for p in e.poly or ())
    mx, my = min(p[0] for p in pts), max(p[0] for p in pts)
    nx, ny = min(p[1] for p in pts), max(p[1] for p in pts)
    r3 = lambda v: round(v, 3)  # noqa: E731
    for e in elements:
        e.x, e.y = r3(e.x - mx), r3(e.y - nx)
        if e.seg:
            e.seg = [[r3(p[0] - mx), r3(p[1] - nx), p[2]] for p in e.seg]
        if e.poly:
            e.poly = [[r3(p[0] - mx), r3(p[1] - nx)] for p in e.poly]
            bx, by, dx, dy = e.box
            e.box = (r3(bx - mx), r3(by - nx), r3(dx), r3(dy))
    return my - mx, ny - nx


# ------------------------------------------------------------- расчёт -----
def build(inp: ConstructionInput):
    """Лента → кольцо. Возвращает (structure, elements, gaps, ring, warnings)."""
    L, W = to_mm(inp.length), to_mm(inp.width)
    if L % 250:
        raise SplitError("Радиальные леса: длина должна быть кратна 0.25 м")
    main_ys = cumulative(split_length(W))
    offsets = [W - y for y in main_ys[:-1]]           # наружные линии стоек от внутренней стороны
    wid: list[ConstructionInput] = []
    if inp.widening:
        if not inp.widening_width or inp.widening_width <= 0:
            raise SplitError("Радиальные леса: укажите вынос уширения")
        offsets += [W + v for v in cumulative(split_length(to_mm(inp.widening_width)))[1:]]
        wid.append(ConstructionInput("widening", inp.length, inp.widening_width,
                                     inp.widening_height or inp.height, pads=inp.pads,
                                     attach_to=1, side="y0", offset=0.0))
    cells, k = choose_cells(L, offsets)
    main = ConstructionInput("facade", inp.length, inp.width, inp.height,
                             inp.intermediate_decks, inp.entrance, inp.pads)
    st, notes = build_group(main, wid, x_bays=cells)
    gen = generate(st)
    elements, gaps, ring = bend(st, gen.elements, k, deck_width=W)
    notes = [("Входная группа закрыта уширением — перенесена на внутреннюю сторону кольца (к объекту), "
              "проверьте проход" if w.startswith("Входная группа закрыта уширением") else w) for w in notes]
    warnings = notes + gen.warnings + _gap_warnings(gaps)
    if k > 1:
        warnings.append(f"Радиальные леса: поворот через {k} ячейки — прямые участки "
                        f"{'/'.join(f'{s / 1000:g}' for s in sorted(set(ring.cells)))} м, середина участка "
                        f"ближе к объекту на {sagitta(ring.cells) / 1000:.2f} м, чем стыки")
    return st, elements, gaps, ring, warnings


def _gap_warnings(gaps: list[dict]) -> list[str]:
    out = []
    seen = set()
    for g in gaps:
        key = (g["offset"], g["gap"], g["ledger"])
        if key in seen or g["dev"] == 0:
            continue
        seen.add(key)
        out.append(f"Радиальные леса: наружный зазор между ячейками {g['gap'] / 1000:g} м "
                   f"(в {g['offset'] / 1000:g} м от внутренней стороны) — вставка ригелем "
                   f"{g['ledger'] / 1000:g} м, разница {abs(g['dev'])} мм "
                   f"({'ригель короче' if g['dev'] > 0 else 'ригель длиннее'}) — проверьте на месте")
    hole = max((g.get("hole", 0) for g in gaps), default=0)
    if hole > HOLE_OK:
        out.append(f"Радиальные леса: клин между ячейками перекрыт планками U00141, но у стоек остаётся "
                   f"щель до {hole / 1000:g} м — проверьте на месте")
    return out


def run_radial(inp: ConstructionInput) -> dict:
    from . import specification
    st, elements, gaps, ring, warnings = build(inp)
    size_x, size_y = _normalize(elements)
    wid_cells = [c for c in st.all_cells() if c.role == "widening"]
    turns = sorted({round(math.degrees(a), 2) for a in ring.turn})
    return {
        "input": {
            "kind": inp.kind, "length": inp.length, "width": inp.width,
            "height": inp.height, "intermediate_decks": inp.intermediate_decks,
            "entrance": inp.entrance, "pads": inp.pads, "widening": inp.widening,
            "widening_width": inp.widening_width, "widening_height": inp.widening_height,
        },
        "grid": {
            # габарит кольца в плане (для размещения на схеме и размеров листа)
            "xs": [0, round(size_x)], "ys": [0, round(size_y)],
            "bays_x": [b - a for a, b in zip(st.xs, st.xs[1:])],
            "bays_y": [b - a for a, b in zip(st.ys, st.ys[1:])],
            "top": st.top + st.lift,
            "decks": sorted(z + st.lift for z in set().union(*(c.decks for c in st.all_cells()))),
            "lift": st.lift,
            "widening_levels": sorted({z + st.lift for c in wid_cells for z in widening_levels(c)}),
            "radial": {
                "cells": len(st.xs) - 1,
                "sections": ring.n,                            # прямых участков (поворотов)
                "per_section": (len(st.xs) - 1) // ring.n,     # ячеек в участке
                "radius": round(ring.r),                       # внутренний радиус, мм
                "turn": turns,                                 # угол поворота в стыках, градусы
                "inserts": sorted({(g["ledger"], g["offset"]) for g in gaps}),
                "max_dev": max((abs(g["dev"]) for g in gaps), default=0),
            },
        },
        "area": {
            "formula": f"{inp.length:g} х {inp.height:g}",
            "value": round(inp.length * inp.height, 3),
        },
        "elements": [e.to_dict() for e in elements],
        "spec": specification(elements),
        "warnings": warnings,
    }
