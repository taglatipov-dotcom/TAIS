"""Генератор строительных лесов: размеры → модель → элементы → спецификация."""
from __future__ import annotations

from . import catalog, spec
from .bays import SplitError
from .constructions import KINDS, SIDES, ConstructionInput, build_group, classify
from .model import widening_levels
from .rules import generate

__all__ = ["ConstructionInput", "SplitError", "KINDS", "SIDES", "classify", "run", "specification"]


def specification(elements) -> dict:
    return spec.build(e.article for e in elements)


def run(inp: ConstructionInput, widenings: list[ConstructionInput] | None = None) -> dict:
    """Полный расчёт одной конструкции (с пристроенными уширениями).
    Возвращает данные, готовые для API."""
    if inp.kind == "radial":
        from .radial import run_radial
        return run_radial(inp)
    st, notes = build_group(inp, widenings or [])
    gen = generate(st)
    wid_cells = [c for c in st.all_cells() if c.role == "widening"]
    length_m = st.length / 1000
    height_m = inp.height
    return {
        "input": {
            "kind": inp.kind, "length": inp.length, "width": inp.width,
            "height": inp.height, "intermediate_decks": inp.intermediate_decks,
            "entrance": inp.entrance, "pads": inp.pads,
        },
        "grid": {
            "xs": st.xs, "ys": st.ys,
            "bays_x": [b - a for a, b in zip(st.xs, st.xs[1:])],
            "bays_y": [b - a for a, b in zip(st.ys, st.ys[1:])],
            "top": st.top + st.lift,
            "decks": sorted(z + st.lift for z in set().union(*(c.decks for c in st.all_cells()))),
            "lift": st.lift,
            # отметки ригелей уширений (через 2 м от нижнего узла и верх)
            "widening_levels": sorted({z + st.lift for c in wid_cells for z in widening_levels(c)}),
        },
        "area": {
            "formula": f"{length_m:g} х {height_m:g}",
            "value": round(length_m * height_m, 3),
        },
        "elements": [e.to_dict() for e in gen.elements],
        "spec": specification(gen.elements),
        "warnings": notes + gen.warnings,
    }
