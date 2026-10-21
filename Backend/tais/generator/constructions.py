"""Рецепты конструкций: из размеров акта строим модель Structure."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .bays import split_length, cumulative
from .bays import SplitError
from .model import BASE_LEVEL, DECK_STEP, MIN_HEIGHT, NODE_STEP, TOP_FLOOR, Cell, Structure

KINDS = {
    "tower": "Башенные",
    "facade": "Фасадные",
    "widening": "Уширение",
    "balcony": "Консольно-опорные леса (балкон)",
    "radial": "Радиальные леса",
}
# Пристраиваемые конструкции: ставятся к грани основной (или к уже стоящим лесам)
ATTACHABLE = ("widening", "balcony")

# Балкон: стойки 2 м — от узла на 0.5 м ниже настила до верха основной конструкции
BALCONY_POST = 2000
BALCONY_BELOW_DECK = 500
BALCONY_BRACE = 2000
# По высоте балкон с диагоналями занимает последний этаж (1.5 м) + диагональ (2.0 м)
BALCONY_ZONE = TOP_FLOOR + BALCONY_BRACE

# Грани основной конструкции, к которым пристраивается уширение
SIDES = {
    "y0": "передняя сторона",   # вдоль длины, меньший Y (сторона входа)
    "y1": "задняя сторона",     # вдоль длины, больший Y
    "x0": "левый торец",        # вдоль ширины, меньший X
    "x1": "правый торец",       # вдоль ширины, больший X
}
OPPOSITE = {"y0": "y1", "y1": "y0", "x0": "x1", "x1": "x0"}


@dataclass
class ConstructionInput:
    kind: str            # tower / facade / widening / balcony
    length: float        # м
    width: float         # м
    height: float        # м — высота конструкции по акту
    intermediate_decks: bool = True  # настилы на каждом ярусе через 2 м
    entrance: bool = True            # входная группа на грани с наименьшим Y
    pads: bool = False               # деревянные подкладки под домкраты (по умолчанию нет)
    # уширение и балкон: к какой конструкции (номер в схеме, None — отдельно), к какой её грани
    # и с какого места вдоль грани (м от начала грани: от меньшего X или меньшего Y).
    # length — вдоль грани, width — вынос от грани.
    attach_to: int | None = None
    side: str = "y0"
    offset: float = 0.0
    # радиальные леса: уширение наружу у каждой ячейки (вынос и высота, м; высота None — как у лесов)
    widening: bool = False
    widening_width: float = 1.0
    widening_height: float | None = None


def to_mm(value_m: float) -> int:
    return int(round(value_m * 1000))


def height_plan(height_mm: int) -> tuple[int, int]:
    """Высота конструкции, кратная 0.5 м, и сдвиг всей конструкции (кроме домкратов).

    Остаток 0.1–0.3 м: строим ниже на остаток и поднимаем на него.
    Остаток 0.4 м: строим на 0.1 м выше и опускаем на 0.1 м.
    Примеры: 6.2 → 6.0 и +0.2; 6.4 → 6.5 и −0.1; 6.0 → 6.0 и 0.
    """
    rest = height_mm % NODE_STEP
    if rest == 0:
        build, shift = height_mm, 0
    elif rest <= 300:
        build, shift = height_mm - rest, rest
    else:
        build, shift = height_mm + (NODE_STEP - rest), -(NODE_STEP - rest)
    if build < NODE_STEP:  # совсем низкая конструкция — не меньше одного узла
        shift -= NODE_STEP - build
        build = NODE_STEP
    return build, shift


def posts_length(height_mm: int) -> int:
    """Суммарная длина стоек = высота конструкции, кратная 0.5 м (см. height_plan)."""
    return height_plan(height_mm)[0]


def deck_levels(top: int, intermediate: bool) -> list[int]:
    """Настилы сверху вниз: последний этаж 1.5 м (верхний настил на 1.5 м ниже верха
    стоек), дальше через 2.0 м.

    Последний (нижний) ярус может получиться ниже 2 м — 0.5, 1.0 или 1.5 м;
    как на него подниматься, решает bottom_floor().
    """
    top_deck = top - TOP_FLOOR
    if top_deck <= BASE_LEVEL:
        return [BASE_LEVEL]
    if not intermediate:
        return [top_deck]
    levels = []
    z = top_deck
    while z > BASE_LEVEL:
        levels.append(z)
        z -= DECK_STEP
    return sorted(levels)


def bottom_floor(decks: list[int]) -> dict | None:
    """Нижний ярус, если он не равен 2 м.

    Ладдер-настил верхнего яруса опускается на этот настил, а сам нижний настил —
    без люка (иначе лестница уйдёт ниже нуля). Высота:
      0.5 м — настил как ступенька;
      1.0 / 1.5 м — нужна отдельная лестница с земли.
    """
    if not decks:
        return None
    low = min(decks)
    height = low - BASE_LEVEL
    if height <= 0 or height >= DECK_STEP:
        return None
    return {"deck": low, "height": height}


def classify(length_m: float, width_m: float) -> str:
    """Правило из документа «Виды конструкций»: башенные — если L/B < 1.5
    или у конструкции всего 4 стойки (по одному пролёту в каждую сторону)."""
    if width_m <= 0:
        return "tower"
    one_bay = max(length_m, width_m) <= 3.0
    ratio = max(length_m, width_m) / min(length_m, width_m)
    return "tower" if ratio < 1.5 or one_bay else "facade"


def build_structure(inp: ConstructionInput, x_breaks: list[int] | None = None,
                    y_breaks: list[int] | None = None,
                    x_bays: list[int] | None = None) -> Structure:
    """x_bays — готовые пролёты по длине (радиальные леса сами подбирают ячейки)."""
    length, width, height = to_mm(inp.length), to_mm(inp.width), to_mm(inp.height)
    if height < MIN_HEIGHT:
        raise SplitError(
            f"Конструкции ниже {MIN_HEIGHT / 1000:g} м пока не поддерживаются — разбираются отдельно")
    xs = cumulative(x_bays) if x_bays else cumulative(split_length(length, x_breaks))
    ys = cumulative(split_length(width, y_breaks))
    top = BASE_LEVEL + posts_length(height)
    if inp.kind == "widening":
        # отдельное уширение: пристраивается к уже стоящей конструкции по стороне y0,
        # там своих стоек нет; без настилов, люков и входной группы
        st = Structure(xs=xs, ys=ys, kind="widening", lift=height_plan(height)[1], pads=inp.pads)
        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                st.cells[(i, j)] = Cell(i=i, j=j, decks=set(), top=top, ground=True,
                                        role="widening", open_side="y0")
        return st
    if inp.kind == "balcony":
        # отдельный балкон к уже стоящим лесам высотой inp.height: своих стоек нет со
        # стороны y0, настил — на уровне верхнего настила стоящих лесов
        _single_bay(inp)
        bottom, deck = balcony_levels(top)
        st = Structure(xs=xs, ys=ys, kind="balcony", lift=height_plan(height)[1], pads=inp.pads)
        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                st.cells[(i, j)] = Cell(i=i, j=j, decks={deck}, top=top, bottom=bottom,
                                        ground=False, role="balcony", open_side="y0")
        return st
    levels = deck_levels(top, inp.intermediate_decks)
    decks = set(levels)
    floor = bottom_floor(levels)
    # люк с лестницей — только там, где лестница (2 м) не уходит ниже первого узла
    hatch = {z for z in decks if z - DECK_STEP >= BASE_LEVEL}

    # Вход — на грани с наименьшим Y; если нужна лестница с земли (нижний ярус 1.0/1.5 м),
    # она стоит у противоположной грани, и вход переносится туда же — с наибольшим Y.
    ground_ladder = floor is not None and floor["height"] in (1000, 1500)
    st = Structure(xs=xs, ys=ys, kind=inp.kind, lift=height_plan(height)[1],
                   entrance_bay=0 if inp.entrance else None,
                   entrance_line=len(ys) - 1 if ground_ladder else 0,
                   pads=inp.pads)
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            access = i == 0 and j == 0
            st.cells[(i, j)] = Cell(i=i, j=j, decks=set(decks), top=top,
                                    ground=True, access=access, role=inp.kind,
                                    hatch_decks=set(hatch) if access else None,
                                    bottom_floor=floor if access else None)
    return st


def balcony_levels(top: int) -> tuple[int, int]:
    """Нижний узел и настил балкона по верху основной конструкции.

    Высоты у балкона нет: он занимает последний этаж. Настил — продолжение верхнего
    настила (на 1.5 м ниже верха стоек), стойки 2 м — от узла на 0.5 м ниже настила
    до верха. Пример: верх 6105 → настил 4605, стойки 4105…6105.
    """
    deck = top - TOP_FLOOR
    bottom = deck - BALCONY_BELOW_DECK
    if bottom <= BASE_LEVEL:
        raise SplitError("Балкон: основная конструкция слишком низкая — нужна высота от 2.5 м")
    return bottom, deck


def _single_bay(inp: ConstructionInput) -> None:
    """Вынос балкона — один пролёт: диагональ под стойкой идёт к основной конструкции."""
    if len(split_length(to_mm(inp.width))) != 1:
        raise SplitError(f"Балкон: вынос {inp.width:g} м должен быть одним пролётом "
                         f"(0.75 / 1.0 / 1.5 / 2.0 / 2.5 / 3.0 м)")


def _snap_height(height_mm: int, lift: int) -> int:
    """Высота уширения на узлах основной конструкции (её сдвиг уже задан): ближайшая
    кратная 0.5 м величина height − lift, не меньше одного узла."""
    build = int(round((height_mm - lift) / NODE_STEP)) * NODE_STEP
    return max(build, NODE_STEP)


def build_group(main: ConstructionInput, widenings: list[ConstructionInput],
                x_bays: list[int] | None = None) -> tuple[Structure, list[str]]:
    """Основная конструкция с пристроенными уширениями и балконами — одна сетка стоек.
    (widenings — все пристройки: kind="widening" или "balcony".)

    Сначала проверяем, попадают ли края уширений на стойки основной конструкции.
    Если нет — основная конструкция перестраивается: её пролёты разбиваются по краям
    уширений (обязательные точки), и об этом выдаётся предупреждение.
    Внутри уширения ригели идут к стойкам основной конструкции, поэтому его пролёты
    вдоль грани совпадают с пролётами основной.
    """
    warnings: list[str] = []
    if not widenings:
        return build_structure(main, x_bays=x_bays), warnings
    L, W = to_mm(main.length), to_mm(main.width)
    x_need: list[int] = []
    y_need: list[int] = []
    taken: dict[str, list[tuple[int, int, ConstructionInput]]] = {}
    under_balcony: set[int] = set()   # номера уширений, над которыми стоит балкон
    for w in widenings:
        if w.side not in SIDES:
            raise SplitError(f"{KINDS[w.kind]}: неизвестная сторона {w.side}")
        if w.kind == "balcony":
            _single_bay(w)
        face = L if w.side in ("y0", "y1") else W
        a = to_mm(w.offset)
        b = a + to_mm(w.length)
        if a < 0 or b > face:
            raise SplitError(
                f"{KINDS[w.kind]} {w.length:g} м с отступом {w.offset:g} м не помещается: "
                f"{SIDES[w.side]} основной конструкции — {face / 1000:g} м")
        for c, d, other in taken.get(w.side, []):
            if a < d and c < b:
                # балкон над уширением на одной стороне — можно, если не пересекаются по высоте
                if {other.kind, w.kind} != {"widening", "balcony"}:
                    raise SplitError(f"Пристройки на стороне «{SIDES[w.side]}» перекрываются")
                under_balcony.add(id(w if w.kind == "widening" else other))
        taken.setdefault(w.side, []).append((a, b, w))
        (x_need if w.side in ("y0", "y1") else y_need).extend([a, b])
        if w.kind == "widening" and to_mm(w.height) < MIN_HEIGHT:
            raise SplitError(
                f"Уширения ниже {MIN_HEIGHT / 1000:g} м пока не поддерживаются")

    # Вынос у пристроек на одной стороне может быть разным: лишние линии сетки от соседей
    # не режут пролёт — ячейка пристройки занимает несколько интервалов сетки (i_end/j_end).

    # проверка «точно по стойкам»: если края уширений не на стойках — перестраиваем
    plain_x = cumulative(x_bays) if x_bays else cumulative(split_length(L))
    plain_y = cumulative(split_length(W))
    x_breaks = None if all(p in plain_x for p in x_need) else x_need
    y_breaks = None if all(p in plain_y for p in y_need) else y_need
    base = build_structure(main, x_breaks, y_breaks, x_bays=None if x_breaks else x_bays)

    def bays(lines):
        return " + ".join(f"{(b - a) / 1000:g}" for a, b in zip(lines, lines[1:]))
    if x_breaks:
        warnings.append(f"Основная конструкция перестроена под пристройку: пролёты по длине "
                        f"{bays(plain_x)} → {bays(base.xs)} м")
    if y_breaks:
        warnings.append(f"Основная конструкция перестроена под пристройку: пролёты по ширине "
                        f"{bays(plain_y)} → {bays(base.ys)} м")

    # линии сетки: основная + вынос уширений наружу
    new_x, new_y = set(base.xs), set(base.ys)
    outward: list[list[int]] = []
    for w in widenings:
        out = cumulative(split_length(to_mm(w.width)))
        if w.side == "y0":
            lines = [-v for v in out]
        elif w.side == "y1":
            lines = [W + v for v in out]
        elif w.side == "x0":
            lines = [-v for v in out]
        else:
            lines = [L + v for v in out]
        outward.append(sorted(lines))
        (new_y if w.side in ("y0", "y1") else new_x).update(lines)
    sx, sy = min(new_x), min(new_y)         # сдвигаем сетку к нулю
    xs = sorted(v - sx for v in new_x)
    ys = sorted(v - sy for v in new_y)
    ix = {v + sx: k for k, v in enumerate(xs)}
    iy = {v + sy: k for k, v in enumerate(ys)}

    st = Structure(xs=xs, ys=ys, kind=base.kind, lift=base.lift,
                   entrance_bay=None if base.entrance_bay is None else ix[base.xs[base.entrance_bay]],
                   entrance_line=iy[base.ys[base.entrance_line]], pads=base.pads)
    for c in base.cells.values():
        c.i, c.j = ix[base.xs[c.i]], iy[base.ys[c.j]]
        st.cells[(c.i, c.j)] = c
    main_top = base.top

    for w, lines in zip(widenings, outward):
        if w.kind == "balcony":
            bottom, deck = balcony_levels(main_top)
            label = f"Балкон {w.length:g}×{w.width:g}"

            def make(i, j):
                return Cell(i=i, j=j, decks={deck}, top=main_top, bottom=bottom, ground=False,
                            role="balcony", open_side=OPPOSITE[w.side])
        else:
            build = _snap_height(to_mm(w.height), base.lift)
            top = BASE_LEVEL + build
            real = (build + base.lift) / 1000
            label = f"Уширение {w.length:g}×{w.width:g}×{w.height:g}"
            if abs(real - w.height) > 1e-6:
                warnings.append(f"{label}: высота {real:g} м — ригели уширения должны попасть "
                                f"в узлы основной конструкции")
            if top > main_top:
                warnings.append(f"{label} выше основной конструкции: стойки основной конструкции "
                                f"на общей стороне наращены до {(top + base.lift) / 1000:g} м")
            if id(w) in under_balcony and top > main_top - BALCONY_ZONE:
                limit = (main_top - BALCONY_ZONE - BASE_LEVEL + base.lift) / 1000
                raise SplitError(
                    f"{label} под балконом: высота не больше {limit:g} м — балкон с диагоналями "
                    f"занимает {BALCONY_ZONE / 1000:g} м от верха основной конструкции")

            def make(i, j, top=top):
                return Cell(i=i, j=j, decks=set(), top=top, ground=True,
                            role="widening", open_side=OPPOSITE[w.side])
        a = to_mm(w.offset)
        b = a + to_mm(w.length)
        # ячейка: пролёт основной вдоль грани × собственный пролёт выноса пристройки
        # (по выносу ячейка может занимать несколько интервалов общей сетки)
        if w.side in ("y0", "y1"):
            along = [ix[v] for v in base.xs if a <= v <= b]
            spans = [((i0, i1), (iy[o0], iy[o1])) for i0, i1 in zip(along, along[1:])
                     for o0, o1 in zip(lines, lines[1:])]
        else:
            along = [iy[v] for v in base.ys if a <= v <= b]
            spans = [((ix[o0], ix[o1]), (j0, j1)) for j0, j1 in zip(along, along[1:])
                     for o0, o1 in zip(lines, lines[1:])]
        for (i0, i1), (j0, j1) in spans:
            new = make(i0, j0)
            new.i_end, new.j_end = i1, j1
            for k in ((i, j) for i in range(i0, i1) for j in range(j0, j1)):
                old = st.cells.get(k)
                if old is None:
                    st.cells[k] = new
                elif ({old.role, new.role} == {"widening", "balcony"} and k not in st.upper):
                    # балкон над уширением: балкон — во втором ярусе ячеек
                    st.cells[k], st.upper[k] = ((old, new) if new.role == "balcony"
                                                else (new, old))
                else:
                    raise SplitError(f"{label} пересекается с другой конструкцией")
    _move_entrance(st, base, [w for w in widenings if w.kind == "widening"], W, warnings)
    return st, warnings


def _move_entrance(st: Structure, base: Structure, widenings: list[ConstructionInput],
                   W: int, warnings: list[str]) -> None:
    """Вход, закрытый уширением, переносится на противоположную грань основной
    конструкции (в том же пролёте), если та свободна."""
    if base.entrance_bay is None:
        return
    x = base.xs[base.entrance_bay]

    def blocked(y_line: int) -> bool:
        side = "y0" if y_line == 0 else "y1"
        return any(w.side == side and to_mm(w.offset) <= x < to_mm(w.offset) + to_mm(w.length)
                   for w in widenings)

    y_now = base.ys[base.entrance_line]
    if not blocked(y_now):
        return
    y_other = W if y_now == 0 else 0
    if blocked(y_other):
        warnings.append("Входная группа закрыта уширениями с обеих сторон — проверьте вход")
        return
    st.entrance_line = st.ys.index(y_other + (st.ys[st.entrance_line] - y_now))
    warnings.append("Входная группа закрыта уширением — перенесена на противоположную сторону")
