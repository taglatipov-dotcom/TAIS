"""Правила раскладки элементов по модели Structure.

Правила подобраны по вашим чертежам из архива ORG_V5 (см. tests/test_archive.py).

Соглашения о вставке блоков (тоже из архива):
  * все блоки вставляются без наклона, только с поворотом вокруг Z;
  * ригель/бортик/диагональ вдоль X: точка — начало ребра (меньший X), поворот 0°;
  * ригель/бортик/диагональ вдоль Y: точка — конец ребра (больший Y), поворот 270°;
  * настил: точка — угол полосы с меньшими X и Y, длина вдоль X, ширина вдоль Y;
  * стойки, стартовые элементы, домкраты — в узле сетки;
  * лестница накидная: смещение (242, 62, 36) мм от угла ячейки с люком, поворот 90°;
  * настил с люком через ярус повёрнут на 180° — вставляется в противоположный угол полосы.

Главные правила:
  * Ригели. Наружная «обшивка» конструкции — ригель в каждом узле через 0.5 м
    по высоте. Ребро наружное на отметке z, если на этой отметке с одной стороны
    ребра есть конструкция, а с другой — нет. Внутренние рёбра — только на
    нижнем узле и под настилами. Поэтому при пристройке балкона общая сторона
    становится внутренней выше настила балкона, и перила там исчезают сами.
  * Бортики — по наружному краю верхнего рабочего настила.
  * Диагонали — во всех крайних пролётах, в полных ярусах по 2 м между настилами.
  * Уширение (role="widening") — без настилов и без перил: ригели только от нижнего
    узла через 2 м и на верху стоек. С открытой стороны (open_side) своих стоек нет —
    ригели крепятся к стойкам основной (или уже стоящей) конструкции. Основную
    конструкцию уширение не меняет: её наружная обшивка на общей стороне остаётся.
  * Балкон (role="balcony") — продолжение верхнего настила наружу: стойки 2 м с наружной
    стороны, с внутренней своих стоек нет. Ригели и бортики — по обычным правилам, поэтому
    на общей стороне перила основной конструкции выше нижнего узла балкона снимаются
    (доступ на балкон). Под каждой наружной стойкой — вертикальная диагональ к основной
    конструкции (в плоскости, перпендикулярной грани), 2.0 м, если помещается.
"""
from __future__ import annotations

from collections import defaultdict

from . import catalog
from .model import (BASE_LEVEL, DECK_STEP, NODE_STEP, Element, Structure, ledger_bottom,
                    widening_levels)

POST_PIECE = 3000                 # основная длина стойки
BOTTOM_POST_SIZES = (1000, 1500, 2000, 2500, 3000)  # есть стойки без наконечника
PLANK_WIDTH = 250
HATCH_WIDTH = 750
LADDER_OFFSET = (242, 62, 36)
GROUND_LADDER_PLANKS = 2           # полосы настила на нуле под лестницей с земли
GROUND_LADDER_DX = 216             # лестница с земли ближе к ригелю x0 на 216 мм
DIAGONAL_EVERY = 1                # 1 — диагональ в каждом крайнем пролёте
DECK_TOLERANCE = 500              # настилы ближе 0.5 м по высоте считаются смежными

ART_POST = "S01062.{:04d}"        # стойка с цельноформованным наконечником
ART_POST_BOTTOM = "S01022.{:04d}"  # стойка без наконечника — нижняя
ART_STARTER = "S01032.0210"
ART_JACK = "U22011.0500"
ART_PAD = "U22061.0300"           # подкладка деревянная под домкрат
ART_LEDGER = "S11013.{:04d}"
ART_PLANK = "U00281.{:04d}"
ART_HATCH = "U00221.{:04d}"
ART_TOEBOARD = "U10012.{:04d}"
ART_DIAGONAL = "S02012.{:03d}{:d}"
ART_LADDER = "U07021.2092"


class Generated:
    def __init__(self) -> None:
        self.elements: list[Element] = []
        self.warnings: list[str] = []

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)

    def add(self, el: Element) -> None:
        if not catalog.exists(el.article):
            self.warn(f"Нет блока {el.article} в каталоге — элемент пропущен")
            return
        self.elements.append(el)


def generate(st: Structure) -> Generated:
    out = Generated()
    _posts(st, out)
    _ledgers(st, out)
    _toeboards(st, out)
    _decks_and_ladders(st, out)
    _diagonals(st, out)
    _join_without_posts(out)
    _balcony_braces(st, out)
    if st.lift:
        _apply_lift(st.lift, out)
    return out


def _apply_lift(dz: int, out: Generated) -> None:
    """Поднять (или опустить) всё, кроме домкратов: высота акта не кратна 0.5 м."""
    for e in out.elements:
        if e.kind == "jack":
            if e.seg:
                e.seg[1][2] += dz  # домкрат на месте, выдвигается до стартового элемента
            continue
        e.z += dz
        if e.seg:
            for p in e.seg:
                p[2] += dz


# ---------------------------------------------------------------- стойки ---
def split_posts(total: int) -> list[int]:
    """Набор стоек снизу вверх: по 3.0 м, короткая — наверху."""
    pieces = [POST_PIECE] * (total // POST_PIECE)
    rest = total % POST_PIECE
    if rest:
        pieces.append(rest)
    return pieces


def _node_cells(st: Structure, il: int, jl: int):
    """Ячейки, у которых узел — угол (узел внутри стороны ячейки с размахом не считается)."""
    seen = set()
    for di in (-1, 0):
        for dj in (-1, 0):
            for c in st.cells_at(il + di, jl + dj):
                if id(c) not in seen and il in (c.i, c.ie) and jl in (c.j, c.je):
                    seen.add(id(c))
                    yield c


def is_widening(c) -> bool:
    return c.role == "widening"


def _node_open(c, il: int, jl: int) -> bool:
    """Узел лежит на открытой стороне ячейки уширения (там нет своих стоек)."""
    return {"y0": jl == c.j, "y1": jl == c.je,
            "x0": il == c.i, "x1": il == c.ie}.get(c.open_side or "", False)


def _x_edge_open(c, jl: int) -> bool:
    return (c.open_side == "y0" and jl == c.j) or (c.open_side == "y1" and jl == c.je)


def _y_edge_open(c, il: int) -> bool:
    return (c.open_side == "x0" and il == c.i) or (c.open_side == "x1" and il == c.ie)


def _posts(st: Structure, out: Generated) -> None:
    for il, x in enumerate(st.xs):
        for jl, y in enumerate(st.ys):
            cells = list(_node_cells(st, il, jl))
            if not cells:
                continue
            if all(c.open_side and _node_open(c, il, jl) for c in cells):
                continue  # открытая сторона уширения/балкона: стойки уже стоят
            # балкон над уширением — отдельные ряды стоек (по высоте не пересекаются)
            for bottom, top, ground in _post_runs(cells):
                _post_column(st, x, y, bottom, top, ground, out)


def _post_runs(cells) -> list[tuple[int, int, bool]]:
    """Сливаем перекрывающиеся по высоте ячейки узла в непрерывные ряды стоек."""
    runs: list[list] = []
    for c in sorted(cells, key=lambda c: c.bottom):
        if runs and c.bottom <= runs[-1][1]:
            runs[-1][1] = max(runs[-1][1], c.top)
            runs[-1][2] = runs[-1][2] or c.ground
        else:
            runs.append([c.bottom, c.top, c.ground])
    return [tuple(r) for r in runs]


def _post_column(st: Structure, x, y, bottom: int, top: int, ground: bool, out: Generated) -> None:
    if ground:
        if st.pads:
            out.add(Element(ART_PAD, x, y, 0, kind="pad"))
        out.add(Element(ART_JACK, x, y, 0, kind="jack",
                        seg=[[x, y, 0], [x, y, BASE_LEVEL]]))
        out.add(Element(ART_STARTER, x, y, 0, kind="starter"))
    z = bottom
    for n, piece in enumerate(split_posts(top - bottom)):
        art = ART_POST.format(piece)
        if n == 0 and ground and piece in BOTTOM_POST_SIZES:
            art = ART_POST_BOTTOM.format(piece)
        out.add(Element(art, x, y, z, kind="post",
                        seg=[[x, y, z], [x, y, z + piece]]))
        z += piece


# ------------------------------------------------------ рёбра ячеек -------
def _merge_runs(n: int, cells_of):
    """Интервалы 0…n−1 вдоль линии → рёбра от стойки до стойки. Соседние интервалы
    с одними и теми же ячейками сливаются: между ними нет угла ячейки, значит нет стойки
    (ячейка с размахом). Возвращает [((a, b), cells)] — ребро от линии a до линии b."""
    out, run = [], None
    for k in range(n):
        cells = cells_of(k)
        key = tuple(sorted(id(c) for c in cells))
        if run is not None and cells and run[2] == key:
            run[1] = k + 1
            continue
        if run is not None and run[3]:
            out.append(((run[0], run[1]), run[3]))
        run = [k, k + 1, key, cells]
    if run is not None and run[3]:
        out.append(((run[0], run[1]), run[3]))
    return out


def _x_edges(st: Structure):
    """Рёбра вдоль X: ((a, b), jl) — от xs[a] до xs[b] на линии ys[jl]."""
    for jl in range(len(st.ys)):
        def cells_of(i, jl=jl):
            return ([c for c in st.cells_at(i, jl - 1) if c.je == jl]
                    + [c for c in st.cells_at(i, jl) if c.j == jl])
        for seg, cells in _merge_runs(len(st.xs) - 1, cells_of):
            yield (seg, jl), cells


def _y_edges(st: Structure):
    """Рёбра вдоль Y: (il, (a, b)) — от ys[a] до ys[b] на линии xs[il]."""
    for il in range(len(st.xs)):
        def cells_of(j, il=il):
            return ([c for c in st.cells_at(il - 1, j) if c.ie == il]
                    + [c for c in st.cells_at(il, j) if c.i == il])
        for seg, cells in _merge_runs(len(st.ys) - 1, cells_of):
            yield (il, seg), cells


def _ledger_levels(st: Structure, cells, edge_open) -> list[int]:
    """Отметки ригелей на ребре. Основная конструкция считается без уширений,
    уширение добавляет свои отметки (кроме открытой стороны без основной конструкции)."""
    if all(c.open_side and edge_open(c) for c in cells):
        return []                     # ригели этой стороны — у стоящей конструкции
    main = [c for c in cells if not is_widening(c)]
    levels = set(_edge_ledger_levels(st, main)) if main else set()
    for c in cells:
        if is_widening(c) and (main or not edge_open(c)):
            levels.update(widening_levels(c))
    return sorted(levels)


def _edge_ledger_levels(st: Structure, cells) -> list[int]:
    lo = min(ledger_bottom(c) for c in cells)
    hi = max(c.top for c in cells)
    levels: set[int] = set()
    for c in cells:
        levels.add(ledger_bottom(c))  # нижний узел (у балкона — под настилом)
        levels.update(c.decks)        # под настилами
    z = lo
    while z <= hi:
        if sum(1 for c in cells if ledger_bottom(c) <= z <= c.top) == 1:
            levels.add(z)             # наружная обшивка
        z += NODE_STEP
    return sorted(levels)


def _place_x(st, seg, jl, z, art_fmt, kind, out):
    x0, x1, y = st.xs[seg[0]], st.xs[seg[1]], st.ys[jl]
    out.add(Element(art_fmt.format(x1 - x0), x0, y, z, 0, kind=kind,
                    seg=[[x0, y, z], [x1, y, z]]))


def _place_y(st, il, seg, z, art_fmt, kind, out):
    x, y0, y1 = st.xs[il], st.ys[seg[0]], st.ys[seg[1]]
    out.add(Element(art_fmt.format(y1 - y0), x, y1, z, 270, kind=kind,
                    seg=[[x, y0, z], [x, y1, z]]))


ENTRANCE_HEIGHT = 2000           # входная группа: проём от нуля до 2 м


def in_entrance(st: Structure, seg: tuple[int, int], jl: int, z: int) -> bool:
    """Ребро грани входа в пролёте входа, ниже 2 м — там проём."""
    return (st.entrance_bay is not None and jl == st.entrance_line
            and seg == (st.entrance_bay, st.entrance_bay + 1)
            and z < BASE_LEVEL + ENTRANCE_HEIGHT)


def _ledgers(st: Structure, out: Generated) -> None:
    for (i, jl), cells in _x_edges(st):
        for z in _ledger_levels(st, cells, lambda c: _x_edge_open(c, jl)):
            if in_entrance(st, i, jl, z):
                continue
            _place_x(st, i, jl, z, ART_LEDGER, "ledger", out)
    for (il, j), cells in _y_edges(st):
        for z in _ledger_levels(st, cells, lambda c: _y_edge_open(c, il)):
            _place_y(st, il, j, z, ART_LEDGER, "ledger", out)


def _toe_levels(cells) -> list[int]:
    """Бортик: верхний настил ячейки, если с другой стороны ребра нет настила рядом."""
    levels = []
    for c in cells:
        if not c.decks:
            continue
        z = max(c.decks)
        others = [o for o in cells if o is not c]
        covered = any(any(abs(d - z) <= DECK_TOLERANCE for d in o.decks) for o in others)
        if not covered:
            levels.append(z)
    return sorted(set(levels))


def _toeboards(st: Structure, out: Generated) -> None:
    for (i, jl), cells in _x_edges(st):
        if all(c.open_side and _x_edge_open(c, jl) for c in cells):
            continue                  # открытая сторона отдельного балкона
        for z in _toe_levels(cells):
            if in_entrance(st, i, jl, z):
                continue
            _place_x(st, i, jl, z, ART_TOEBOARD, "toeboard", out)
    for (il, j), cells in _y_edges(st):
        if all(c.open_side and _y_edge_open(c, il) for c in cells):
            continue
        for z in _toe_levels(cells):
            _place_y(st, il, j, z, ART_TOEBOARD, "toeboard", out)


# --------------------------------------------------- настилы, лестницы ----
def has_builtin_ladder(article: str) -> bool:
    """Настилы с люком 2.5 и 3.0 м идут сразу с лестницей (видно по наименованию)."""
    return "лестниц" in catalog.name_of(article).lower()


def _hatch(st: Structure, c, z: int, turned: bool, out: Generated) -> int:
    """Настил с люком (и лестница, если она не встроена). Возвращает занятую ширину.

    Соседние ярусы чередуются поворотом на 180° вокруг Z — иначе не подняться.
    Повёрнутый блок вставляется в противоположный угол той же полосы.
    """
    x0, y0, x1, _ = st.cell_box(c)
    dx = x1 - x0
    art = ART_HATCH.format(dx)
    if turned:
        ix, iy, rot = x1, y0 + HATCH_WIDTH, 180
    else:
        ix, iy, rot = x0, y0, 0
    out.add(Element(art, ix, iy, z, rot, kind="hatch", box=(x0, y0, dx, HATCH_WIDTH)))
    if not has_builtin_ladder(art):
        lx, ly, lz = LADDER_OFFSET
        if turned:
            out.add(Element(ART_LADDER, x1 - lx, y0 + HATCH_WIDTH - ly, z + lz, 270, kind="ladder"))
        else:
            out.add(Element(ART_LADDER, x0 + lx, y0 + ly, z + lz, 90, kind="ladder"))
    return HATCH_WIDTH


def _decks_and_ladders(st: Structure, out: Generated) -> None:
    for c in st.all_cells():
        x0, y0, x1, y1 = st.cell_box(c)
        dx, dy = x1 - x0, y1 - y0
        hatch_levels = c.decks if c.hatch_decks is None else c.hatch_decks
        hatch_order = sorted(hatch_levels, reverse=True)  # сверху вниз
        floor = c.bottom_floor if c.access else None
        ground_ladder = floor is not None and floor["height"] in (1000, 1500)
        for z in sorted(c.decks):
            used = 0
            if c.access and z in hatch_levels:
                if dy >= HATCH_WIDTH and catalog.exists(ART_HATCH.format(dx)):
                    turned = hatch_order.index(z) % 2 == 1
                    used = _hatch(st, c, z, turned, out)
                else:
                    out.warn(f"Ячейка {dx / 1000:g}×{dy / 1000:g} м: настил с люком не помещается")
            # полосы стального настила: при люке — сразу за ним
            y = y0 + used
            # на нижнем ярусе 1.0/1.5 м две крайние полосы со стороны y1 переносятся на ноль
            stop = y1 - GROUND_LADDER_PLANKS * PLANK_WIDTH if (ground_ladder and z == floor["deck"]) else y1
            while y + PLANK_WIDTH <= stop:
                out.add(Element(ART_PLANK.format(dx), x0, y, z, 0, kind="deck",
                                box=(x0, y, dx, PLANK_WIDTH)))
                y += PLANK_WIDTH
            if stop == y1 and y < y1:
                out.warn(f"Настил {dx / 1000:g} м: остался зазор {y1 - y} мм по ширине")
        if ground_ladder:
            _ground_ladder(st, c, floor, out)


def _ground_ladder(st: Structure, c, floor: dict, out: Generated) -> None:
    """Подъём на нижний ярус 1.0 / 1.5 м.

    Две полосы настила со стороны, противоположной люку (край y1), лежат на нулевой
    отметке (первый узел); на них опирается накидная лестница U07021.2092 (подъём 2 м),
    зацепленная у ригеля стороны x0 на отметке первый узел + 2 м.
    """
    x0, y0, x1, y1 = st.cell_box(c)
    dx = x1 - x0
    if y1 - y0 < GROUND_LADDER_PLANKS * PLANK_WIDTH:
        out.warn("Ячейка доступа слишком узкая для лестницы с земли")
        return
    for k in range(GROUND_LADDER_PLANKS, 0, -1):
        y = y1 - k * PLANK_WIDTH
        out.add(Element(ART_PLANK.format(dx), x0, y, BASE_LEVEL, 0, kind="deck",
                        box=(x0, y, dx, PLANK_WIDTH)))
    hook = BASE_LEVEL + DECK_STEP
    lx, ly, lz = LADDER_OFFSET
    # Лестница у ригеля стороны x0 (напротив края x1), спускается в сторону +X;
    # ширина (0.33 м по локальной X блока) ложится вдоль Y внутри перенесённых полос.
    strip_y0 = y1 - GROUND_LADDER_PLANKS * PLANK_WIDTH
    out.add(Element(ART_LADDER, x0 + lx - GROUND_LADDER_DX, strip_y0 + ly, hook + lz, 90,
                    kind="ladder"))
    if st.exists(c.i - 1, c.j):
        out.warn(f"Лестница с земли цепляется за внутренний ригель на {hook / 1000:g} м — "
                 f"проверьте, что он есть")


# ------------------------------------------------------------ диагонали ---
def lifts_for(cells) -> list[tuple[int, int]]:
    """Ярусы для диагоналей: между соседними настилами (и нижним узлом).

    Берём только полные ярусы по 2.0 м; если таких нет (низкая конструкция) —
    ярусы от 1.0 м (диагоналей на 0.5 м для большинства пролётов нет).
    """
    bottom = min(c.bottom for c in cells)
    decks = sorted(set().union(*(c.decks for c in cells)))
    return _lifts([bottom] + [d for d in decks if d > bottom])


def _lifts(marks: list[int]) -> list[tuple[int, int]]:
    pairs = [(a, b - a) for a, b in zip(marks, marks[1:])]
    full = [(z, h) for z, h in pairs if h == DECK_STEP]
    if full:
        return full
    return [(z, h - h % NODE_STEP) for z, h in pairs if h >= 2 * NODE_STEP]


def _pick(indices: list[int]) -> set[int]:
    """Из ряда крайних пролётов берём первый, последний и каждый N-й."""
    if not indices:
        return set()
    picked = {indices[0], indices[-1]}
    picked.update(idx for k, idx in enumerate(indices) if k % DIAGONAL_EVERY == 0)
    return picked


def _diagonals(st: Structure, out: Generated) -> None:
    """Диагонали на противоположных гранях направлены в противоположные стороны.

    Грань с меньшим Y — поворот 0° (подъём к +X), с большим Y — 180° (подъём к −X);
    грань с меньшим X — 270° (подъём к −Y), с большим X — 90° (подъём к +Y),
    как в ваших чертежах (2.0х2.0х4.2).
    """
    def edge_lifts(cells, edge_open):
        """Ярусы диагоналей на ребре и ячейка, чья это грань; ([], None) — ребро не крайнее.
        Основная конструкция — как без уширения; уширение — по своим ригелям через 2 м,
        только на своих наружных гранях (не на открытой стороне)."""
        main = [c for c in cells if c.role not in ("widening", "balcony") or not c.open_side]
        if main:
            ground = [c for c in main if c.ground]
            return (lifts_for(main), ground[0]) if len(ground) == 1 else ([], None)
        wid = [c for c in cells if is_widening(c)]
        if len(wid) == 1 and not edge_open(wid[0]):
            return _lifts(widening_levels(wid[0])), wid[0]
        return [], None

    rows: dict[int, list] = defaultdict(list)
    for (i, jl), cells in _x_edges(st):
        lifts, owner = edge_lifts(cells, lambda c: _x_edge_open(c, jl))
        if lifts:
            # грань с большим Y своей ячейки — диагональ в обратную сторону
            rows[jl].append((i, lifts, owner.je == jl))
    for jl, edges in rows.items():
        chosen = _pick([e[0] for e in edges])
        for i, lifts, mirrored in edges:
            if i not in chosen:
                continue
            x0, x1, y = st.xs[i[0]], st.xs[i[1]], st.ys[jl]
            for z, h in lifts:
                art = ART_DIAGONAL.format((x1 - x0) // 10, h // NODE_STEP)
                if mirrored:
                    out.add(Element(art, x1, y, z, 180, kind="diagonal",
                                    seg=[[x1, y, z], [x0, y, z + h]]))
                else:
                    out.add(Element(art, x0, y, z, 0, kind="diagonal",
                                    seg=[[x0, y, z], [x1, y, z + h]]))

    cols: dict[int, list] = defaultdict(list)
    for (il, j), cells in _y_edges(st):
        lifts, owner = edge_lifts(cells, lambda c: _y_edge_open(c, il))
        if lifts:
            # грань с большим X своей ячейки — диагональ в обратную сторону
            cols[il].append((j, lifts, owner.ie == il))
    for il, edges in cols.items():
        chosen = _pick([e[0] for e in edges])
        for j, lifts, mirrored in edges:
            if j not in chosen:
                continue
            x, y0, y1 = st.xs[il], st.ys[j[0]], st.ys[j[1]]
            for z, h in lifts:
                art = ART_DIAGONAL.format((y1 - y0) // 10, h // NODE_STEP)
                if mirrored:
                    out.add(Element(art, x, y0, z, 90, kind="diagonal",
                                    seg=[[x, y0, z], [x, y1, z + h]]))
                else:
                    out.add(Element(art, x, y1, z, 270, kind="diagonal",
                                    seg=[[x, y1, z], [x, y0, z + h]]))


# ---------------------------------------- склейка в местах без стоек ------
_JOIN_ART = {"ledger": ART_LEDGER, "toeboard": ART_TOEBOARD}


def _post_cover(out: Generated) -> dict[tuple[float, float], list[tuple[float, float]]]:
    cover: dict[tuple[float, float], list] = defaultdict(list)
    for e in out.elements:
        if e.kind == "post" and e.seg:
            cover[(e.x, e.y)].append((e.seg[0][2], e.seg[1][2]))
    return cover


def _has_post(cover, x, y, z) -> bool:
    return any(a <= z <= b for a, b in cover.get((x, y), ()))


def _span(e: Element) -> tuple[str, float, float, float]:
    """Ось, координата линии и отрезок вдоль неё (по сегменту элемента)."""
    (x0, y0, _), (x1, y1, _) = e.seg
    if y0 == y1:
        return "x", y0, min(x0, x1), max(x0, x1)
    return "y", x0, min(y0, y1), max(y0, y1)


def _rebuild(e: Element, a: float, b: float) -> Element | None:
    """Тот же элемент на отрезке [a, b] вдоль своей линии (по соглашениям о вставке)."""
    axis, line, _, _ = _span(e)
    length = int(round(b - a))
    z = e.z
    if e.kind in _JOIN_ART:
        art = _JOIN_ART[e.kind].format(length)
        if axis == "x":
            el = Element(art, a, line, z, 0, kind=e.kind, seg=[[a, line, z], [b, line, z]])
        else:
            el = Element(art, line, b, z, 270, kind=e.kind, seg=[[line, a, z], [line, b, z]])
    else:                                   # диагональ: направление сохраняем
        h = int(round(e.seg[1][2] - e.seg[0][2]))
        art = ART_DIAGONAL.format(length // 10, h // NODE_STEP)
        if axis == "x":
            el = (Element(art, a, line, z, 0, kind="diagonal", seg=[[a, line, z], [b, line, z + h]])
                  if e.rot == 0 else
                  Element(art, b, line, z, 180, kind="diagonal", seg=[[b, line, z], [a, line, z + h]]))
        else:
            el = (Element(art, line, a, z, 90, kind="diagonal", seg=[[line, a, z], [line, b, z + h]])
                  if e.rot == 90 else
                  Element(art, line, b, z, 270, kind="diagonal", seg=[[line, b, z], [line, a, z + h]]))
    return el if catalog.exists(art) else None


def _join_without_posts(out: Generated) -> None:
    """Ригель, бортик или диагональ рвутся только на стойке. Если два соседних куска
    сходятся в узле, где на этой отметке стойки нет (например, под балконом другого
    выноса — его стойки начинаются выше), куски склеиваются в один элемент."""
    cover = _post_cover(out)
    groups: dict[tuple, list[Element]] = defaultdict(list)
    keep: list[Element] = []
    for e in out.elements:
        if e.kind in ("ledger", "toeboard", "diagonal") and e.seg:
            axis, line, _, _ = _span(e)
            h = e.seg[1][2] - e.seg[0][2]
            groups[(e.kind, axis, line, e.z, h, e.rot)].append(e)
        else:
            keep.append(e)
    joined: list[Element] = []
    for (kind, axis, line, z, h, _), items in groups.items():
        items.sort(key=lambda e: _span(e)[2])
        cur = items[0]
        for nxt in items[1:]:
            _, _, a0, b0 = _span(cur)
            _, _, a1, b1 = _span(nxt)
            jx, jy = (b0, line) if axis == "x" else (line, b0)
            if (b0 == a1 and not _has_post(cover, jx, jy, z)
                    and not _has_post(cover, jx, jy, z + h)):
                merged = _rebuild(cur, a0, b1)
                if merged is not None:
                    cur = merged
                    continue
            joined.append(cur)
            cur = nxt
        joined.append(cur)
    out.elements = keep + joined


# ------------------------------------------------- диагонали балкона ------
BRACE_HEIGHTS = (2000, 1500, 1000)   # предпочтительно 2.0 м


def _balcony_braces(st: Structure, out: Generated) -> None:
    """Под каждой наружной стойкой балкона — вертикальная диагональ к основной конструкции.

    Диагональ лежит в плоскости, перпендикулярной грани: верхний конец — на стойке
    балкона на уровне настила (на 0.5 м выше низа стойки), нижний — на стойке основной
    конструкции на h ниже. Балкон с диагоналями занимает 1.5 + 2.0 = 3.5 м по высоте.
    Вставка — по тем же соглашениям, что у обычных диагоналей (подъём к балкону).
    """
    done: set[tuple] = set()
    for c in st.all_cells():
        if c.role != "balcony" or not c.open_side:
            continue
        x0, y0, x1, y1 = st.cell_box(c)
        bay = (y1 - y0) if c.open_side in ("y0", "y1") else (x1 - x0)
        zt = ledger_bottom(c)          # уровень настила балкона
        h = next((h for h in BRACE_HEIGHTS if zt - h >= BASE_LEVEL
                  and catalog.exists(ART_DIAGONAL.format(bay // 10, h // NODE_STEP))), None)
        if h is None:
            out.warn(f"Балкон: диагональ {bay / 1000:g} м под стойкой не помещается — "
                     f"основная конструкция низкая")
            continue
        art = ART_DIAGONAL.format(bay // 10, h // NODE_STEP)
        z = zt - h
        if c.open_side == "y1":        # балкон с меньшим Y, подъём к −Y
            lines = [(x, y1, z, 270, [[x, y1, z], [x, y0, zt]]) for x in (x0, x1)]
        elif c.open_side == "y0":      # балкон с большим Y, подъём к +Y
            lines = [(x, y0, z, 90, [[x, y0, z], [x, y1, zt]]) for x in (x0, x1)]
        elif c.open_side == "x1":      # балкон с меньшим X, подъём к −X
            lines = [(x1, y, z, 180, [[x1, y, z], [x0, y, zt]]) for y in (y0, y1)]
        else:                          # балкон с большим X, подъём к +X
            lines = [(x0, y, z, 0, [[x0, y, z], [x1, y, zt]]) for y in (y0, y1)]
        for x, y, zz, rot, seg in lines:
            key = (x, y, rot)
            if key in done:
                continue
            done.add(key)
            out.add(Element(art, x, y, zz, rot, kind="diagonal", seg=seg))
