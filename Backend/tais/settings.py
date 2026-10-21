"""Настройки пользователя: %APPDATA%\\TAIS\\settings.json."""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

DEFAULTS = {
    # папка с библиотекой заготовок (там лежит Шаблон.dwg с блоками элементов);
    # пусто — встроенная библиотека (папка Library в сборке, см. builtin_library_dir)
    "library_dir": "",
    "template_name": "Шаблон.dwg",
    # куда сохранять готовые схемы: чертежи — в подпапку DWG, PDF — в подпапку PDF
    "output_dir": str(Path.home() / "Documents" / "TAIS"),
    # точка привязки модели в шаблоне, мм — как у примера в Шаблон.dwg
    "model_origin": [1754, 1277, 0],
    # основная надпись: заводы (краткое имя -> полное), год и префикс номера ИС
    "refineries": [
        {"short": "УНПЗ", "full": "ПАО АНК \"Башнефть\" \"Башнефть-УНПЗ\""},
        {"short": "Новойл", "full": "ПАО АНК \"Башнефть\" \"Башнефть-Новойл\""},
        {"short": "УОС", "full": "ПАО Уфаоргсинтез"},
        {"short": "УНХ", "full": "ПАО АНК \"Башнефть\" \"Башнефть-Уфанефтехим\""},
    ],
    "year": date.today().year,
    "isp_prefix": "П1-02",
    # принтер для печати схем; пусто — как в листах шаблона. PDF-принтер — PDF в подпапку PDF
    "printer": "",
}


def app_dir() -> Path:
    if os.environ.get("TAIS_HOME"):  # для тестов и переносной установки
        base = Path(os.environ["TAIS_HOME"])
    elif sys.platform == "win32" and os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"]) / "TAIS"
    else:
        base = Path.home() / ".tais"
    base.mkdir(parents=True, exist_ok=True)
    return base


def builtin_library_dir() -> Path | None:
    """Встроенная библиотека: Шаблон.dwg и «Веса элементов.csv», поставляются с программой.

    В установленной программе путь передаёт Electron (TAIS_LIBRARY_DIR = resources\\library),
    при разработке — папка Library в корне проекта.
    """
    env = os.environ.get("TAIS_LIBRARY_DIR")
    candidates = [Path(env)] if env else []
    candidates.append(Path(__file__).resolve().parents[2] / "Library")
    for p in candidates:
        if p.is_dir():
            return p
    return None


def settings_path() -> Path:
    return app_dir() / "settings.json"


def load() -> dict:
    data = dict(DEFAULTS)
    p = settings_path()
    if p.exists():
        try:
            data.update(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass  # испорченный файл — работаем на значениях по умолчанию
    # своя папка не указана или пропала — работаем со встроенной библиотекой
    lib = data.get("library_dir") or ""
    builtin = builtin_library_dir()
    data["library_builtin"] = bool(builtin) and (not lib or not Path(lib).is_dir())
    if data["library_builtin"]:
        data["library_dir"] = str(builtin)
    if not data.get("output_dir"):
        data["output_dir"] = DEFAULTS["output_dir"]
    return data


def save(values: dict) -> dict:
    data = load()
    data.update({k: v for k, v in values.items() if k in DEFAULTS})
    # встроенную библиотеку не запоминаем путём: после переустановки в другую папку путь бы устарел
    builtin = builtin_library_dir()
    if builtin and data.get("library_dir") and Path(data["library_dir"]).resolve() == builtin.resolve():
        data["library_dir"] = ""
    stored = {k: v for k, v in data.items() if k in DEFAULTS}
    settings_path().write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")
    return load()


def template_path(data: dict | None = None) -> Path | None:
    data = data or load()
    if not data.get("library_dir"):
        return None
    return Path(data["library_dir"]) / data.get("template_name", DEFAULTS["template_name"])
