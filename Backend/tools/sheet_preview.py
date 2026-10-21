"""Предпросмотр листа A3 без nanoCAD: виды, масштабы и размеры в SVG.

Запуск (из папки Backend):
    ..\\.venv\\Scripts\\python tools\\sheet_preview.py 21x1x4.7 2x1x10.2 12x3x4.2+12x3x4.2
Для каждой схемы в папке tools\\preview появится <размеры>.svg — откройте в браузере.
Конструкции одной схемы — через «+», размеры — длина x ширина x высота в метрах.
Рамки экранов взяты из Шаблон.dwg (views.TEMPLATE_A3).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tais.cad import views as V  # noqa: E402
from tais.generator.scheme import run_scheme  # noqa: E402

ORIGIN = (1754.0, 1277.0, 0.0)
SHEET_W, SHEET_H = 420.0, 297.0
OUT_DIR = Path(__file__).with_name("preview")
COLORS = {"post": "#222", "ledger": "#2b6cb0", "diagonal": "#c05621", "toeboard": "#2f855a"}


def _clip(p, q, box):
    """Отсечение отрезка прямоугольником (Лианг — Барски)."""
    x0, y0, x1, y1 = box
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pp == 0:
            if qq < 0:
                return None
            continue
        t = qq / pp
        if pp < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return ((p[0] + t0 * dx, p[1] + t0 * dy), (p[0] + t1 * dx, p[1] + t1 * dy))


def _segments(e):
    if e.get("seg"):
        a, b = e["seg"]
        yield a, b
    elif e.get("box"):
        x, y, dx, dy = e["box"]
        z = e["z"]
        c = [(x, y, z), (x + dx, y, z), (x + dx, y + dy, z), (x, y + dy, z)]
        for k in range(4):
            yield c[k], c[(k + 1) % 4]


def _line(a, b, color, width):
    return (f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" '
            f'stroke="{color}" stroke-width="{width}"/>')


def render(items: list[dict], title: str) -> str:
    res = run_scheme(items)
    sheet = V.plan_sheet(V.TEMPLATE_A3, res["elements"], res["parts"], ORIGIN)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SHEET_W} {SHEET_H}" '
           f'width="{SHEET_W * 3}" height="{SHEET_H * 3}" font-family="Arial">',
           f'<rect width="{SHEET_W}" height="{SHEET_H}" fill="white"/>',
           f'<g transform="translate(0,{SHEET_H}) scale(1,-1)">',
           '<rect x="20" y="5" width="395" height="287" fill="none" stroke="#000" stroke-width="0.5"/>']
    labels = []   # (x, y, текст, цвет, размер шрифта) в координатах листа
    for name, s in sheet["slots"].items():
        x0, y0 = s.center[0] - s.width / 2, s.center[1] - s.height / 2
        out.append(f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{s.width:.2f}" height="{s.height:.2f}" '
                   f'fill="none" stroke="#bbb" stroke-dasharray="2 1" stroke-width="0.3"/>')
        v = sheet["views"].get(name)
        if v is None:
            continue
        box = (x0, y0, x0 + s.width, y0 + s.height)
        labels.append((x0 + 1.5, y0 + s.height - 4, f"{name} 1:{v.scale}", "#555", 3, "start"))
        for e in res["elements"]:
            col = COLORS.get(e.get("kind"), "#777")
            for a, b in _segments(e):
                pa = v.to_paper((a[0] + ORIGIN[0], a[1] + ORIGIN[1], a[2] + ORIGIN[2]))
                pb = v.to_paper((b[0] + ORIGIN[0], b[1] + ORIGIN[1], b[2] + ORIGIN[2]))
                c = _clip(pa, pb, box)
                if c:
                    out.append(_line(c[0], c[1], col, 0.15))
    red = "#d00"
    for d in sheet["dims"]:
        if d.kind == "ordinate":   # выноска с изломом и подпись за её концом
            (fx, fy), (lx, ly) = d.p1, d.line
            jog = lx - 3.0
            out.append(_line((fx + 0.6, fy), (jog - 1.5, fy), red, 0.12))
            out.append(_line((jog - 1.5, fy), (jog, ly), red, 0.12))
            out.append(_line((jog, ly), (lx, ly), red, 0.12))
            labels.append((lx + 0.8, ly, d.text, red, 2.5, "start"))
            continue
        if d.rotation == 0:
            ly = d.line[1]
            ends = ((d.p1[0], ly), (d.p2[0], ly))
            tx, ty = (d.p1[0] + d.p2[0]) / 2, ly + 1.5
        else:
            lx = d.line[0]
            ends = ((lx, d.p1[1]), (lx, d.p2[1]))
            tx, ty = lx - 1.5, (d.p1[1] + d.p2[1]) / 2
        out.append(_line(d.p1, ends[0], red, 0.12))
        out.append(_line(d.p2, ends[1], red, 0.12))
        out.append(_line(ends[0], ends[1], red, 0.18))
        for px, py in ends:
            out.append(_line((px - 0.8, py - 0.8), (px + 0.8, py + 0.8), red, 0.3))
        labels.append((tx, ty, d.text, red, 2.5, "middle"))
    out.append("</g>")
    for x, y, text, color, size, anchor in labels:
        out.append(f'<text x="{x:.2f}" y="{SHEET_H - y:.2f}" font-size="{size}" fill="{color}" '
                   f'text-anchor="{anchor}" dominant-baseline="middle">{text}</text>')
    out.append(f'<text x="25" y="10" font-size="4">{title}</text>')
    out.append("</svg>")
    return "\n".join(out)


def parse(arg: str) -> list[dict]:
    items = []
    for part in arg.split("+"):
        l, w, h = (float(v.replace(",", ".")) for v in part.lower().replace("х", "x").split("x"))
        items.append({"length": l, "width": w, "height": h})
    return items


def main(args: list[str]) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    for arg in args or ["21x1x4.7"]:
        path = OUT_DIR / f"{arg}.svg"
        path.write_text(render(parse(arg), arg), encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main(sys.argv[1:])
