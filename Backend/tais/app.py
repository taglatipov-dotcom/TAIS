"""FastAPI-приложение: API + раздача собранного фронтенда."""
from __future__ import annotations

import base64
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, acts, db, demo, settings, stats
from .cad import nanocad
from .generator import KINDS, SplitError, spec as spec_mod
from .generator.scheme import run_scheme

log = logging.getLogger("tais")

app = FastAPI(title="TAIS", version=__version__)

# Демо-версия: после окончания срока API закрыто (кроме проверки сервера и статуса демо)
_DEMO_OPEN = ("/api/health", "/api/demo")


@app.middleware("http")
async def demo_guard(request, call_next):
    path = request.url.path
    if path.startswith("/api/") and not path.startswith(_DEMO_OPEN):
        st = demo.status()
        if st["expired"]:
            return JSONResponse(status_code=403, content={"code": "demo_expired", "message": demo_message(st)})
    return await call_next(request)


def demo_message(st: dict) -> str:
    if st.get("reason") == "clock":
        return "Дата на компьютере переведена назад. Установите правильную дату и перезапустите TAIS."
    return f"Срок демо-версии закончился {st.get('until')}. Обратитесь к разработчику за полной версией."


# ------------------------------------------------------------------ модели --
class ConstructionItem(BaseModel):
    kind: str = Field("auto", description="auto / tower / facade / widening / balcony / radial")
    length: float = Field(..., gt=0, le=200, description="Длина, м (у уширения — вдоль грани)")
    width: float = Field(..., gt=0, le=10, description="Ширина, м (у уширения — вынос от грани)")
    # у пристроенного балкона высоты нет (по верху основной) — поле можно не передавать
    height: float | None = Field(None, gt=0, le=60, description="Высота, м")
    intermediate_decks: bool = True
    entrance: bool = True
    pads: bool = False
    # уширение/балкон: номер основной конструкции в списке (0/None — отдельно), грань и отступ
    attach_to: int | None = Field(None, ge=0)
    side: Literal["y0", "y1", "x0", "x1"] = "y0"
    offset: float = Field(0, ge=0, le=200, description="Отступ от начала грани, м")
    # радиальные леса: уширение наружу у каждой ячейки
    widening: bool = False
    widening_width: float = Field(1.0, gt=0, le=10, description="Вынос уширения, м")
    widening_height: float | None = Field(None, gt=0, le=60, description="Высота уширения, м (нет — как у лесов)")


class SchemeRequest(BaseModel):
    constructions: list[ConstructionItem]


class ActIn(BaseModel):
    number: str = Field(..., min_length=1)
    date: str = Field(..., min_length=1)
    refinery: str = ""
    department: str = ""
    facility: str = ""
    location: str = ""
    constructions: list[ConstructionItem] = []
    isp_number: int | None = None


class PictureIn(BaseModel):
    data_url: str


class FileIn(BaseModel):
    data_url: str


class CadFile(BaseModel):
    path: str
    close: bool = False    # печать: после печати закрыть файл с сохранением


class IspStart(BaseModel):
    start: int = Field(..., ge=1)


class SettingsModel(BaseModel):
    library_dir: str = ""
    template_name: str = "Шаблон.dwg"
    output_dir: str = ""
    model_origin: list[float] = [1754, 1277, 0]
    refineries: list[dict] = []
    year: int = 2026
    isp_prefix: str = "П1-02"
    printer: str = ""


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, {"code": code, "message": message})


def _scheme(items: list[ConstructionItem]) -> dict:
    # веса и наименования — из «Веса элементов.csv» в папке библиотеки, если он есть
    spec_mod.refresh(settings.load().get("library_dir"))
    for it in items:
        if it.kind not in ("auto", *KINDS):
            raise _err(400, "bad_kind", f"Неизвестный тип: {it.kind}")
    for n, it in enumerate(items, 1):
        if it.height is None:
            if it.kind == "balcony" and it.attach_to:
                it.height = 0.0       # не используется: балкон по верху основной
            else:
                raise _err(400, "no_height", f"Конструкция {n}: укажите высоту")
    try:
        return run_scheme([it.model_dump() for it in items])
    except (SplitError, ValueError) as exc:
        raise _err(400, "bad_size", str(exc))


def _safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or "схема"


def _cad_build(result: dict, out_name: str, extras: dict | None = None) -> dict:
    conf = settings.load()
    tpl = settings.template_path(conf)
    if tpl is None:
        raise _err(400, "template_missing", "Укажите папку библиотеки заготовок в настройках.")
    # чертежи — в подпапку DWG, PDF при печати — в соседнюю PDF (nanocad.pdf_name)
    out_dir = Path(conf["output_dir"] or settings.DEFAULTS["output_dir"]) / nanocad.DWG_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{_safe_name(out_name)}.dwg"
    extras = dict(extras or {})
    extras.setdefault("parts", result.get("parts"))   # для масштаба видов и размеров листа A3
    return _cad(nanocad.build, result["elements"], tpl, out, conf["model_origin"], extras)


def _cad(fn, *args):
    try:
        return fn(*args)
    except nanocad.CadError as exc:
        status = 409 if exc.code in ("nanocad_not_installed", "nanocad_unsupported_os",
                                     "gen_py_cache") else 400
        raise _err(status, exc.code, exc.message)


# --------------------------------------------------------- общее, nanoCAD --
@app.get("/api/health")
def health():
    return {"ok": True, "version": __version__}


@app.get("/api/demo")
def demo_status():
    st = demo.status()
    st["message"] = demo_message(st) if st["expired"] else None
    return st


@app.get("/api/settings")
def get_settings():
    return settings.load()


@app.put("/api/settings")
def put_settings(body: SettingsModel):
    return settings.save(body.model_dump())


@app.post("/api/scheme")
def scheme(req: SchemeRequest):
    return _scheme(req.constructions)


@app.post("/api/cad/clear-gen-py")
def cad_clear_gen_py():
    """Удалить кэш COM-обёрток gen_py (после этого TAIS нужно перезапустить)."""
    return nanocad.clear_gen_py()


@app.get("/api/elements")
def elements_info():
    """Откуда берутся веса и наименования спецификации."""
    path = spec_mod.refresh(settings.load().get("library_dir"))
    return {"file": path, "expected_name": spec_mod.ELEMENTS_FILE}


@app.put("/api/elements-file")
def put_elements_file(body: FileIn):
    """Загрузить «Веса элементов.csv» (файл спецификации) в папку библиотеки."""
    lib = settings.load().get("library_dir")
    if not lib or not Path(lib).is_dir():
        raise _err(400, "no_library", "Сначала укажите расположение файла шаблона")
    m = re.match(r"^data:[^,]*;base64,(.+)$", body.data_url, re.S)
    if not m:
        raise _err(400, "bad_file", "Ожидается файл CSV")
    data = base64.b64decode(m.group(1))
    target = Path(lib) / spec_mod.ELEMENTS_FILE
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(data)
    try:
        rows = spec_mod.load_elements_file(tmp)
    except (OSError, UnicodeDecodeError, ValueError):
        rows = {}
    if not rows:
        tmp.unlink(missing_ok=True)
        raise _err(400, "bad_file", "В файле нет строк с артикулами. Нужен CSV в UTF-8 с разделителем «;» "
                                    "и столбцами «Артикул», «Наименование в спецификации», «Вес».")
    tmp.replace(target)
    return elements_info()


@app.get("/api/cad/status")
def cad_status():
    """nanoCAD, шаблон, файл спецификации и папка схем — для флагов в шапке и в настройках."""
    conf = settings.load()
    st = nanocad.status()
    tpl = settings.template_path(conf)
    st["template"] = str(tpl) if tpl else None
    st["template_ok"] = bool(tpl and tpl.exists())
    lib = conf.get("library_dir") or ""
    st["library_dir"] = lib
    st["library_ok"] = bool(lib and Path(lib).is_dir())
    st["library_builtin"] = bool(conf.get("library_builtin"))
    builtin = settings.builtin_library_dir()
    st["builtin_library"] = str(builtin) if builtin else None
    out = conf.get("output_dir") or settings.DEFAULTS["output_dir"]
    st["output_dir"] = out
    st["output_ok"] = bool(out)
    st["spec_file"] = spec_mod.refresh(lib)
    st["spec_ok"] = bool(st["spec_file"])
    st["spec_expected"] = spec_mod.ELEMENTS_FILE
    st["first_run"] = not settings.settings_path().exists()
    return st


def _dwg(path: str) -> Path:
    p = Path(path)
    if p.suffix.lower() != ".dwg":
        raise _err(400, "bad_file", "Ожидается файл DWG")
    return p


@app.post("/api/cad/show")
def cad_show(body: CadFile):
    """Открыть готовую схему в nanoCAD и сделать окно активным."""
    return _cad(nanocad.show, _dwg(body.path))


@app.post("/api/cad/print")
def cad_print(body: CadFile):
    """Распечатать листы схемы; close=True — затем закрыть файл с сохранением."""
    return _cad(nanocad.print_file, _dwg(body.path), body.close, settings.load().get("printer", ""))


@app.get("/api/cad/printers")
def cad_printers():
    """Принтеры nanoCAD для выбора в настройках (nanoCAD запускается, если не запущен)."""
    tpl = settings.template_path()
    if tpl is None:
        raise _err(400, "template_missing", "Укажите расположение файла шаблона в настройках.")
    return _cad(nanocad.printers, tpl)


@app.post("/api/cad/build")
def cad_build(req: SchemeRequest):
    """Чертёж без акта — для быстрой проверки генератора."""
    result = _scheme(req.constructions)
    name = "_".join(f"{c.length:g}х{c.width:g}" + ("" if c.kind == "balcony" else f"х{c.height or 0:g}")
                    for c in req.constructions)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    info = _cad_build(result, f"{name}_{stamp}", {"spec": result["spec"]})
    return {"file": info, "spec": result["spec"], "warnings": result["warnings"]}


# ------------------------------------------------------------------- акты --
def _act_or_404(act_id: int) -> dict:
    act = db.get_act(act_id)
    if act is None:
        raise _err(404, "not_found", "Акт не найден")
    return act


def _decorate(act: dict, conf: dict | None = None) -> dict:
    conf = conf or settings.load()
    act = dict(act)
    act["isp_full"] = acts.full_isp_number(act, conf)
    act["location_full"] = acts.full_location(act)
    act["refinery_full"] = acts.refinery_full(act.get("refinery", ""), conf)
    act["area"] = acts.area(act["constructions"])
    act["has_picture"] = bool(act.get("picture") and Path(act["picture"]).exists())
    return act


@app.get("/api/acts")
def list_acts(status: str | None = None):
    conf = settings.load()
    return [_decorate(a, conf) for a in db.list_acts(status)]


@app.post("/api/acts")
def create_act(body: ActIn):
    return _decorate(db.create_act(body.model_dump()))


@app.post("/api/acts/isp-numbers")
def assign_isp(body: IspStart):
    """Назначить номера ИС актам без номера, по порядку (как в ORG_V5)."""
    conf = settings.load()
    return [_decorate(a, conf) for a in db.assign_isp_numbers(body.start)]


@app.get("/api/acts/isp-last")
def isp_last():
    """Наибольший назначенный номер ИС — чтобы не листать список до конца."""
    act = stats.max_isp(db.list_acts())
    if act is None:
        return {"isp_number": None, "isp_full": None, "act_id": None, "number": None, "next": None}
    return {"isp_number": act["isp_number"], "isp_full": acts.full_isp_number(act, settings.load()),
            "act_id": act["id"], "number": act["number"], "next": act["isp_number"] + 1}


@app.get("/api/stats")
def get_stats(days: int = 30):
    """Аналитика: схемы по дням за последние days дней, итоги и разбивки."""
    data = stats.compute(db.list_acts(), days=max(7, min(days, 366)))
    data["max_isp_full"] = None
    if data["max_isp_act"]:
        act = db.get_act(data["max_isp_act"])
        data["max_isp_full"] = acts.full_isp_number(act, settings.load()) if act else None
    return data


@app.get("/api/acts/{act_id}")
def get_act(act_id: int):
    return _decorate(_act_or_404(act_id))


@app.put("/api/acts/{act_id}")
def update_act(act_id: int, body: ActIn):
    _act_or_404(act_id)
    return _decorate(db.update_act(act_id, body.model_dump()))


@app.delete("/api/acts/{act_id}")
def delete_act(act_id: int):
    act = _act_or_404(act_id)
    if act.get("picture"):
        Path(act["picture"]).unlink(missing_ok=True)
    db.delete_act(act_id)
    return {"ok": True}


@app.put("/api/acts/{act_id}/picture")
def put_picture(act_id: int, body: PictureIn):
    """Ситуационный план: картинка из буфера обмена (data URL)."""
    _act_or_404(act_id)
    m = re.match(r"^data:image/(png|jpeg|jpg|bmp);base64,(.+)$", body.data_url, re.S)
    if not m:
        raise _err(400, "bad_picture", "Ожидается картинка PNG, JPG или BMP")
    ext = "jpg" if m.group(1) in ("jpeg", "jpg") else m.group(1)
    path = db.pictures_dir() / f"act_{act_id}.{ext}"
    path.write_bytes(base64.b64decode(m.group(2)))
    return _decorate(db.update_act(act_id, {"picture": str(path)}))


@app.get("/api/acts/{act_id}/picture")
def get_picture(act_id: int):
    act = _act_or_404(act_id)
    if not act.get("picture") or not Path(act["picture"]).exists():
        raise _err(404, "no_picture", "У акта нет ситуационного плана")
    return FileResponse(act["picture"])


@app.get("/api/acts/{act_id}/preview")
def act_preview(act_id: int):
    act = _decorate(_act_or_404(act_id))
    items = [ConstructionItem(**c) for c in act["constructions"]]
    return {"act": act, "scheme": _scheme(items) if items else None,
            "fields": acts.title_fields(act, settings.load())}


@app.post("/api/acts/{act_id}/build")
def act_build(act_id: int):
    conf = settings.load()
    act = _decorate(_act_or_404(act_id), conf)
    if not act["constructions"]:
        raise _err(400, "no_constructions", "В акте нет конструкций")
    if act["isp_number"] is None:
        raise _err(400, "no_isp", "Сначала назначьте акту номер исполнительной схемы")
    result = _scheme([ConstructionItem(**c) for c in act["constructions"]])
    extras = {
        "fields": acts.title_fields(act, conf),
        "area_rows": acts.area_rows(act["constructions"]),
        "area_text": act["area"]["text"],
        "picture": act["picture"] if act["has_picture"] else None,
        "spec": result["spec"],
    }
    info = _cad_build(result, act["isp_full"], extras)
    updated = db.update_act(act_id, {
        "status": "done", "file_path": info["path"],
        "done_at": datetime.now().isoformat(timespec="seconds"),
    })
    return {"file": info, "act": _decorate(updated, conf), "warnings": result["warnings"]}


@app.post("/api/acts/{act_id}/reopen")
def act_reopen(act_id: int):
    _act_or_404(act_id)
    return _decorate(db.update_act(act_id, {"status": "new"}))


@app.exception_handler(HTTPException)
async def http_error(_, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=detail)


# ------------------------------------------------------- фронтенд (SPA) -----
def static_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "tais" / "static"


_static = static_dir()
if (_static / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise _err(404, "not_found", "Нет такого адреса API")
        file = _static / path
        if path and file.is_file():
            return FileResponse(file)
        return FileResponse(_static / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def no_frontend():
        return JSONResponse({"message": "Фронтенд не собран. Для разработки запустите Vite (npm run dev)."})
