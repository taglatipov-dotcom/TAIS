"""Модель конструкции: сетка стоек + ячейки с настилами.

Конструкция хранится не как чертёж, а как данные:
  * xs, ys — координаты осей стоек (мм);
  * cells  — ячейки сетки (i, j) с набором отметок настилов.

Элементы (стойки, ригели, настилы, бортики, диагонали) выводятся из модели
правилами в rules.py. Перила ставятся только на внешних краях настилов:
поэтому при пристройке балкона перила на общей стороне исчезают сами.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Отметка первого узла (ригеля) над нулём, мм — как в ваших чертежах (105)
BASE_LEVEL = 105
# Шаг узлов (розеток) по высоте, мм
NODE_STEP = 500
# Шаг между рабочими настилами, мм
DECK_STEP = 2000
# Высота последнего (верхнего) этажа над верхним настилом, мм
TOP_FLOOR = 1500
# Минимальная высота конструкции по акту, мм (ниже — разбирается отдельно)
MIN_HEIGHT = 1500


@dataclass
class Cell:
    i: int
    j: int
    decks: set[int] = field(default_factory=set)  # отметки настилов, мм
    top: int = 0                                   # отметка верха стоек, мм
    bottom: int = BASE_LEVEL                       # отметка нижнего узла, мм
    ground: bool = True                            # опирается на землю
    access: bool = False                           # ячейка с люком и лестницей
    # отметки, где в ячейке доступа лежит настил с люком (None — на всех настилах)
    hatch_decks: set[int] | None = None
    # нижний ярус ниже 2 м: {"deck": отметка, "height": 500/1000/1500}
    bottom_floor: dict | None = None
    role: str = "tower"                            # tower / facade / balcony / widening
    # уширение: сторона ячейки без своих стоек (y0/y1/x0/x1) — там ригели крепятся
    # к стойкам существующей конструкции
    open_side: str | None = None
    # ячейка может занимать несколько интервалов сетки (пристройки разного выноса на
    # одной стороне дают лишние линии сетки): i…i_end, j…j_end; None — один интервал
    i_end: int | None = None
    j_end: int | None = None

    @property
    def ie(self) -> int:
        return self.i + 1 if self.i_end is None else self.i_end

    @property
    def je(self) -> int:
        return self.j + 1 if self.j_end is None else self.j_end


def ledger_bottom(c: Cell) -> int:
    """Нижний ряд ригелей ячейки. У балкона нижнего ряда нет — ригели начинаются
    под настилом (стойки при этом идут от узла на 0.5 м ниже настила)."""
    if c.role == "balcony" and c.decks:
        return min(c.decks)
    return c.bottom


def widening_levels(c: Cell) -> list[int]:
    """Ригели уширения: от нижнего узла через 2 м и на верху стоек.
    Пример: уширение 5 м — отметки 0, 2, 4 и 5 м от нижнего узла."""
    return sorted({*range(c.bottom, c.top, DECK_STEP), c.top})


@dataclass
class Structure:
    xs: list[int]
    ys: list[int]
    cells: dict[tuple[int, int], Cell] = field(default_factory=dict)
    kind: str = "tower"
    # сдвиг всей конструкции по высоте, кроме домкратов (мм): +100…+300 или −100
    lift: int = 0
    # входная группа: номер пролёта (None — без входа) и линия грани по Y (индекс в ys)
    entrance_bay: int | None = None
    entrance_line: int = 0
    # деревянные подкладки под домкраты
    pads: bool = False
    # второй ярус ячеек: балкон над уширением в том же месте плана
    upper: dict[tuple[int, int], Cell] = field(default_factory=dict)

    def cells_at(self, i: int, j: int) -> list[Cell]:
        """Все ячейки в месте плана (i, j): основная/уширение и балкон над ним."""
        return [c for c in (self.cells.get((i, j)), self.upper.get((i, j))) if c is not None]

    def all_cells(self) -> list[Cell]:
        out, seen = [], set()
        for c in (*self.cells.values(), *self.upper.values()):
            if id(c) not in seen:          # ячейка с размахом записана под несколькими ключами
                seen.add(id(c))
                out.append(c)
        return out

    # --- геометрия ячеек ---------------------------------------------------
    def cell_box(self, c: Cell) -> tuple[int, int, int, int]:
        return self.xs[c.i], self.ys[c.j], self.xs[c.ie], self.ys[c.je]

    def has_deck(self, i: int, j: int, z: int) -> bool:
        c = self.cells.get((i, j))
        return c is not None and z in c.decks

    def exists(self, i: int, j: int) -> bool:
        return (i, j) in self.cells

    def spans(self, c: Cell, z: int) -> bool:
        """Ячейка занимает отметку z (между нижним узлом и верхом стоек)."""
        return c.bottom <= z <= c.top

    # --- размеры для подписи и таблиц -------------------------------------
    @property
    def length(self) -> int:
        return self.xs[-1] - self.xs[0]

    @property
    def width(self) -> int:
        return self.ys[-1] - self.ys[0]

    @property
    def top(self) -> int:
        return max((c.top for c in self.all_cells()), default=0)


@dataclass
class Element:
    """Одна вставка блока nanoCAD."""
    article: str
    x: float
    y: float
    z: float
    rot: float = 0        # поворот вокруг вертикали, градусы (0/90/180/270; у радиальных — любой)
    kind: str = ""        # post / ledger / deck / toeboard / diagonal / ladder / jack / starter
    # отрезок для предпросмотра (в мм): [[x1,y1,z1],[x2,y2,z2]]
    seg: list[list[float]] | None = None
    # габарит настила в плане для предпросмотра: (x_min, y_min, dx, dy)
    box: tuple[float, float, float, float] | None = None
    # повёрнутый настил (радиальные леса): углы в плане [[x, y], …]; box — его габарит
    poly: list[list[float]] | None = None

    def to_dict(self) -> dict:
        d = {
            "article": self.article, "x": self.x, "y": self.y, "z": self.z,
            "rot": self.rot, "kind": self.kind,
        }
        if self.seg is not None:
            d["seg"] = self.seg
        if self.box is not None:
            d["box"] = list(self.box)
        if self.poly is not None:
            d["poly"] = self.poly
        return d
