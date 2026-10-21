"""Спецификация: количество по артикулам, наименования и веса, порядок строк.

Наименования для спецификации и веса берутся из файла «Веса элементов.csv»
в папке библиотеки (рядом с Шаблон.dwg). Если файла нет — из встроенного каталога.
"""
from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

from . import catalog

ELEMENTS_FILE = "Веса элементов.csv"

# Порядок групп в спецификации (по префиксу артикула).
# Подтверждено: подкладки, домкраты, ригели, диагонали, настилы, лестницы.
# Стартовые элементы и стойки поставлены после домкратов, бортики — после настилов
# (уточняется у пользователя).
SPEC_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("подкладки", ("U22061",)),
    ("домкраты", ("U22011",)),
    ("стартовые элементы", ("S01032",)),
    ("стойки", ("S01022", "S01062", "S01081", "S01091")),
    ("ригели", ("S11013", "S11041")),
    ("диагонали", ("S02012", "S02032")),
    ("настилы", ("U00221", "U00281", "U00141", "U00161")),
    ("бортики", ("U10012", "U10071")),
    ("лестницы", ("U07021", "U07041")),
]

_overrides: dict[str, tuple[str | None, float | None]] = {}
_loaded: tuple[str, float] | None = None


def _group_index(article: str) -> int:
    prefix = article.split(".")[0]
    for n, (_, prefixes) in enumerate(SPEC_GROUPS):
        if prefix in prefixes:
            return n
    return len(SPEC_GROUPS)


def sort_key(article: str):
    return (_group_index(article), article)


def _parse_weight(text: str) -> float | None:
    text = (text or "").strip().replace(",", ".").replace(" ", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_elements_file(path: Path) -> dict[str, tuple[str | None, float | None]]:
    """Артикул -> (наименование в спецификации, вес). Разделитель «;», кодировка UTF-8."""
    out: dict[str, tuple[str | None, float | None]] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    if not rows:
        return out
    head = [h.strip().lower() for h in rows[0]]

    def col(*names: str) -> int | None:
        for i, h in enumerate(head):
            if any(n in h for n in names):
                return i
        return None

    i_art = col("артикул")
    # имя берём только из столбца «Наименование в спецификации»;
    # обычный столбец «Наименование» — это имя блока, для спецификации не годится
    i_name = col("наименование в спецификации")
    i_w = col("вес")
    if i_art is None:
        return out
    for r in rows[1:]:
        if i_art >= len(r) or not re.match(r"^[SU]\d{5}\.\d{4}$", r[i_art].strip()):
            continue
        name = r[i_name].strip() if i_name is not None and i_name < len(r) and r[i_name].strip() else None
        weight = _parse_weight(r[i_w]) if i_w is not None and i_w < len(r) else None
        out[r[i_art].strip()] = (name, weight)
    return out


def refresh(library_dir: str | None) -> str | None:
    """Подхватить файл весов из папки библиотеки (перечитывается при изменении)."""
    global _overrides, _loaded
    if not library_dir:
        _overrides, _loaded = {}, None
        return None
    path = Path(library_dir) / ELEMENTS_FILE
    if not path.exists():
        _overrides, _loaded = {}, None
        return None
    mtime = path.stat().st_mtime
    if _loaded != (str(path), mtime):
        _overrides = load_elements_file(path)
        _loaded = (str(path), mtime)
    return str(path)


def default_spec_name(article: str) -> str:
    """Наименование для спецификации по правилу (сверено с вашей PDF-спецификацией):
    «Ригель S (2.0м)» -> «S3 Ригель (2.0м)», «Элемент стартовый S» -> «S2 Элемент стартовый»."""
    name = catalog.name_of(article)
    if name == article:
        return name
    if article.startswith(("S01", "S02")):
        prefix = "S2"
    elif article.startswith("S11"):
        prefix = "S3"
    elif article.startswith("U10"):
        prefix = "U2"
    elif article.startswith("U"):
        prefix = "U1"
    else:
        prefix = ""
    name = re.sub(r"\s+S(?=\s|$)", "", name).strip()
    name = name.replace("градусов(", "градусов (")
    return f"{prefix} {name}".strip()


def spec_name(article: str) -> str:
    name = _overrides.get(article, (None, None))[0]
    return name or default_spec_name(article)


def weight(article: str) -> float | None:
    w = _overrides.get(article, (None, None))[1]
    return w if w is not None else catalog.weight_of(article)


def build(articles) -> dict:
    """Спецификация по списку артикулов (по одному на каждую вставку блока)."""
    counts = Counter(articles)
    rows, total, unknown = [], 0.0, []
    for art in sorted(counts, key=sort_key):
        w = weight(art)
        qty = counts[art]
        if w is None:
            unknown.append(art)
        else:
            total += w * qty
        rows.append({
            "article": art,
            "name": spec_name(art),
            "qty": qty,
            "unit_weight": w,
            "total_weight": round(w * qty, 2) if w is not None else None,
        })
    return {"rows": rows, "total_weight": round(total, 2),
            "unknown_weights": len(unknown), "unknown_articles": unknown}
