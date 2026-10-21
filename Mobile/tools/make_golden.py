"""Эталоны для проверки JS-генератора мобильного приложения.

Считает набор схем Python-генератором (Backend/tais/generator) и пишет результат
в Mobile/tests/golden.json. Запуск из корня проекта:
    .venv\\Scripts\\python Mobile\\tools\\make_golden.py
затем в папке Mobile: npm test
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend"))

from tais.generator import spec  # noqa: E402
from tais.generator.bays import SplitError  # noqa: E402
from tais.generator.scheme import run_scheme  # noqa: E402

T = {"kind": "tower", "length": 3, "width": 1, "height": 6}

CASES: dict[str, list[dict]] = {
    "tower 2x2x6": [{"kind": "tower", "length": 2, "width": 2, "height": 6}],
    "auto 6x2x6.2": [{"kind": "auto", "length": 6, "width": 2, "height": 6.2}],
    "auto 2x1x4.7": [{"kind": "auto", "length": 2, "width": 1, "height": 4.7}],
    "tower 2x2x6.4 no entrance pads": [{"kind": "tower", "length": 2, "width": 2, "height": 6.4,
                                        "entrance": False, "pads": True}],
    "tower 3x1.5x3.3": [{"kind": "tower", "length": 3, "width": 1.5, "height": 3.3}],
    "tower 2.5x2.5x1.8": [{"kind": "tower", "length": 2.5, "width": 2.5, "height": 1.8}],
    "facade 9x1x18 no decks": [{"kind": "facade", "length": 9, "width": 1, "height": 18,
                                "intermediate_decks": False}],
    "facade 13.5x1.5x11.9": [{"kind": "facade", "length": 13.5, "width": 1.5, "height": 11.9}],
    "facade 7.25x0.75x5.6": [{"kind": "facade", "length": 7.25, "width": 0.75, "height": 5.6}],
    "widening alone": [{"kind": "widening", "length": 3, "width": 1, "height": 5}],
    "balcony alone": [{"kind": "balcony", "length": 3, "width": 1, "height": 6}],
    "widening y0": [T, {"kind": "widening", "length": 3, "width": 1, "height": 5,
                        "attach_to": 1, "side": "y0", "offset": 0}],
    "widening rebuild y1": [{"kind": "tower", "length": 3, "width": 2, "height": 6.2},
                            {"kind": "widening", "length": 1.5, "width": 1, "height": 5,
                             "attach_to": 1, "side": "y1", "offset": 1.5}],
    "widening x0 x1": [{"kind": "facade", "length": 6, "width": 2, "height": 8.3},
                       {"kind": "widening", "length": 2, "width": 1.5, "height": 4,
                        "attach_to": 1, "side": "x0", "offset": 0},
                       {"kind": "widening", "length": 1, "width": 0.75, "height": 9.7,
                        "attach_to": 1, "side": "x1", "offset": 1}],
    "balcony y0": [T, {"kind": "balcony", "length": 3, "width": 1, "height": 6,
                       "attach_to": 1, "side": "y0", "offset": 0}],
    "balcony x1": [{"kind": "facade", "length": 6, "width": 2, "height": 10.2},
                   {"kind": "balcony", "length": 2, "width": 1.5, "height": None,
                    "attach_to": 1, "side": "x1", "offset": 0}],
    "balcony over widening": [{"kind": "facade", "length": 6, "width": 1, "height": 18},
                              {"kind": "balcony", "length": 6, "width": 1, "height": 0,
                               "attach_to": 1, "side": "y0", "offset": 0},
                              {"kind": "widening", "length": 3, "width": 1, "height": 4,
                               "attach_to": 1, "side": "y0", "offset": 0}],
    "different reach": [{"kind": "tower", "length": 3, "width": 2, "height": 10},
                        {"kind": "balcony", "length": 3, "width": 2, "height": 0,
                         "attach_to": 1, "side": "y0", "offset": 0},
                        {"kind": "balcony", "length": 3, "width": 1, "height": 0,
                         "attach_to": 1, "side": "y1", "offset": 0},
                        {"kind": "widening", "length": 3, "width": 3, "height": 4,
                         "attach_to": 1, "side": "y0", "offset": 0}],
    "two separate": [{"kind": "auto", "length": 4, "width": 2, "height": 7.1},
                     {"kind": "auto", "length": 12, "width": 1, "height": 4.4}],
    "radial 24x1x6": [{"kind": "radial", "length": 24, "width": 1, "height": 6}],
    "radial 30 widening": [{"kind": "radial", "length": 30, "width": 1, "height": 6.2,
                            "widening": True, "widening_width": 1}],
    "radial 60x1.5x10": [{"kind": "radial", "length": 60, "width": 1.5, "height": 10}],
    "radial 12.75": [{"kind": "radial", "length": 12.75, "width": 1, "height": 4,
                      "widening": True, "widening_width": 1.5, "widening_height": 2.5}],
    "radial 100": [{"kind": "radial", "length": 100, "width": 1, "height": 8}],
    # ошибки
    "err low": [{"kind": "tower", "length": 2, "width": 2, "height": 1.0}],
    "err balcony bay": [{"kind": "balcony", "length": 3, "width": 3.5, "height": 6}],
    "err offset": [T, {"kind": "widening", "length": 3, "width": 1, "height": 5,
                       "attach_to": 1, "side": "y0", "offset": 1}],
    "err attach": [T, {"kind": "widening", "length": 3, "width": 1, "height": 5, "attach_to": 5}],
    "err under balcony": [{"kind": "facade", "length": 6, "width": 1, "height": 18},
                          {"kind": "balcony", "length": 6, "width": 1, "height": 0,
                           "attach_to": 1, "side": "y0", "offset": 0},
                          {"kind": "widening", "length": 3, "width": 1, "height": 15,
                           "attach_to": 1, "side": "y0", "offset": 0}],
    "err split": [{"kind": "tower", "length": 2.1, "width": 2, "height": 6}],
}


def main() -> None:
    spec.refresh(str(ROOT / "Library"))
    out = {}
    for name, items in CASES.items():
        items = [dict(it) for it in items]
        for it in items:          # как app._scheme: у пристроенного балкона высоты нет
            if it.get("height") is None and it.get("kind") == "balcony" and it.get("attach_to"):
                it["height"] = 0.0
        try:
            out[name] = {"items": items, "result": run_scheme(items)}
        except (SplitError, ValueError) as exc:
            out[name] = {"items": items, "error": str(exc)}
    path = ROOT / "Mobile" / "tests" / "golden.json"
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"{len(out)} эталонов → {path}")


if __name__ == "__main__":
    main()
