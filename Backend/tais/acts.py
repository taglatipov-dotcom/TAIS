"""Данные акта для основной надписи схемы (по образцу ORG_V5)."""
from __future__ import annotations


def refinery_full(short: str, conf: dict) -> str:
    for r in conf.get("refineries", []):
        if r.get("short") == short:
            return r.get("full") or short
    return short


# служебные слова не дают букву в аббревиатуре: «Цех по переработке» -> «ЦП»
_SKIP_WORDS = {"и", "в", "во", "на", "по", "с", "со", "для", "из", "к", "от", "при"}


def abbreviate(text: str) -> str:
    """Несколько слов -> аббревиатура для номера ИС.

    «Цех №2» -> «Ц№2», «Объект 5» -> «О5», «Цех каталитического крекинга» -> «ЦКК».
    Слова с цифрами, знаком № или уже написанные заглавными («ЭЛОУ-АВТ-6») берутся целиком.
    Одно слово («36-1-2», «ГФУ», «Битумная») не меняется.
    """
    words = (text or "").split()
    if len(words) < 2:
        return (text or "").strip()
    out = ""
    for w in words:
        if any(ch.isdigit() for ch in w) or "№" in w or (w.isupper() and len(w) > 1):
            out += w
        elif w.lower() in _SKIP_WORDS:
            continue
        else:
            letter = next((ch for ch in w if ch.isalpha()), "")
            out += letter.upper()
    return out


def full_isp_number(act: dict, conf: dict) -> str | None:
    """П1-02-Новойл-Ц№2-36-1-2-ИС2180-2026 — формат из ORG_V5.

    Цех и установка из нескольких слов сокращаются (abbreviate); пустые части пропускаются.
    """
    if act.get("isp_number") is None:
        return None
    parts = [conf.get("isp_prefix", "П1-02"), act.get("refinery", ""),
             abbreviate(act.get("department", "")), abbreviate(act.get("facility", "")),
             f"ИС{act['isp_number']}", str(conf.get("year", ""))]
    return "-".join(p.strip() for p in parts if p and str(p).strip())


def full_location(act: dict) -> str:
    """«Цех №2. 36-1-2. Доп. место. » — как в ORG_V5."""
    out = ""
    for key in ("department", "facility", "location"):
        val = (act.get(key) or "").strip()
        if val:
            out += f"{val}. "
    return out


BALCONY_HEIGHT = 2.0   # у балкона своей высоты нет — в площадь идёт высота его стоек


def area_rows(constructions: list[dict]) -> list[dict]:
    """Строки таблицы площади: у балкона вместо высоты — высота его стоек (2 м)."""
    return [dict(c, height=BALCONY_HEIGHT) if c.get("kind") == "balcony" else c
            for c in constructions]


def area(constructions: list[dict]) -> dict:
    """Площадь: длина × высота по каждой конструкции и сумма (формат ORG_V5)."""
    terms, products, total = [], [], 0.0
    for c in area_rows(constructions):
        a, h = float(c["length"]), float(c.get("height") or 0)
        terms.append(f"{a:g} х {h:g}")
        products.append(round(a * h, 3))
        total += a * h
    total = round(total, 3)
    if len(terms) > 1:
        text = f"{' + '.join(terms)} = {' + '.join(f'{p:g}' for p in products)} = {total:g}"
    elif terms:
        text = f"{terms[0]} = {total:g}"
    else:
        text = ""
    return {"text": text, "value": total}


def title_fields(act: dict, conf: dict) -> dict[str, str]:
    """Метки шаблона nanoCAD -> текст (те же метки, что в шаблоне ORG_V5)."""
    return {
        "[Date]": act.get("date", ""),
        "[Act]": act.get("number", ""),
        "[Isp_number]": full_isp_number(act, conf) or "",
        "[Zavod]": refinery_full(act.get("refinery", ""), conf),
        "[Location]": full_location(act),
    }
