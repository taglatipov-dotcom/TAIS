"""Схема из нескольких конструкций: каждая считается отдельно и ставится следующей по Y
(друг за другом, зазор 1 м, выровнены по началу X) — tais.cad.views.arrange."""
from __future__ import annotations

from . import spec
from .constructions import ATTACHABLE, KINDS, SIDES, ConstructionInput, classify
from .bays import SplitError
from . import run

GAP = 1000  # зазор между конструкциями на схеме, мм


def specification_from_dicts(elements: list[dict]) -> dict:
    return spec.build(e["article"] for e in elements)


def _shift(e: dict, dx: float, dy: float = 0.0) -> dict:
    e = dict(e)
    e["x"] += dx
    e["y"] += dy
    if "seg" in e:
        e["seg"] = [[p[0] + dx, p[1] + dy, p[2]] for p in e["seg"]]
    if "box" in e:
        b = e["box"]
        e["box"] = [b[0] + dx, b[1] + dy, b[2], b[3]]
    return e


def _input(it: dict) -> ConstructionInput:
    kind = it.get("kind") or "auto"
    if kind == "auto":
        kind = classify(it["length"], it["width"])
    return ConstructionInput(kind, it["length"], it["width"], it["height"],
                             it.get("intermediate_decks", True), it.get("entrance", True),
                             it.get("pads", False), it.get("attach_to") or None,
                             it.get("side") or "y0", float(it.get("offset") or 0),
                             bool(it.get("widening", False)),
                             float(it.get("widening_width") or 1.0),
                             it.get("widening_height") or None)


def run_scheme(items: list[dict]) -> dict:
    """items: [{kind: auto/tower/facade/widening/balcony/radial, length, width, height,
    intermediate_decks?, entrance?, pads?, attach_to?, side?, offset?,
    widening?, widening_width?, widening_height? (радиальные: уширение наружу)}]

    Уширение или балкон с attach_to (номер конструкции в списке, с 1) считается вместе
    с ней — одной сеткой стоек; без attach_to — отдельной конструкцией.
    """
    from ..cad.views import arrange   # чистая геометрия, без nanoCAD

    if not items:
        raise ValueError("Добавьте хотя бы одну конструкцию")
    inputs = [_input(it) for it in items]
    attached: dict[int, list[int]] = {}
    for n, inp in enumerate(inputs, 1):
        if inp.kind not in ATTACHABLE or not inp.attach_to:
            inp.attach_to = None
            continue
        t = inp.attach_to
        if t == n or not 1 <= t <= len(inputs):
            raise SplitError(f"Конструкция {n}: {KINDS[inp.kind].lower()} пристроено к "
                             f"несуществующей конструкции №{t}")
        if inputs[t - 1].kind in (*ATTACHABLE, "radial"):
            raise SplitError(f"Конструкция {n}: пристраивать можно только к башенным или "
                             f"фасадным лесам (№{t} — {KINDS[inputs[t - 1].kind].lower()})")
        attached.setdefault(t, []).append(n)

    results: list[dict] = []
    parts: list[dict] = []
    warnings: list[str] = []
    for n, (it, inp) in enumerate(zip(items, inputs), 1):
        if inp.attach_to:
            continue                    # считается вместе с основной конструкцией
        wids = attached.get(n, [])
        res = run(inp, [inputs[k - 1] for k in wids])
        results.append(res)
        prefix = f"Конструкция {n}: " if len(items) > 1 else ""
        warnings.extend(prefix + w for w in res["warnings"])
        parts.append({
            "n": n, "kind": inp.kind, "kind_label": KINDS[inp.kind],
            "length": it["length"], "width": it["width"], "height": it["height"],
            "grid": res["grid"],
            "widenings": [{
                "n": k, "kind": inputs[k - 1].kind, "kind_label": KINDS[inputs[k - 1].kind],
                "length": inputs[k - 1].length, "width": inputs[k - 1].width,
                "height": inputs[k - 1].height, "side": inputs[k - 1].side,
                "side_label": SIDES[inputs[k - 1].side], "offset": inputs[k - 1].offset,
            } for k in wids],
        })

    elements: list[dict] = []
    for part, res, (dx, dy) in zip(parts, results, arrange(parts, gap=GAP)):
        part["offset"], part["offset_y"] = dx, dy
        elements.extend(_shift(e, dx, dy) for e in res["elements"])
    return {
        "parts": parts,
        "elements": elements,
        "spec": specification_from_dicts(elements),
        "warnings": warnings,
    }
