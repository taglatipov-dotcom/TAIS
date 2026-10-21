"""Локальная база актов: %APPDATA%\\TAIS\\tais.db (SQLite, у каждого пользователя своя)."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from .settings import app_dir

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS acts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    number        TEXT    NOT NULL,           -- номер акта
    date          TEXT    NOT NULL,           -- дата акта, ДД.ММ.ГГГГ
    refinery      TEXT    NOT NULL DEFAULT '',-- завод (краткое имя из настроек)
    department    TEXT    NOT NULL DEFAULT '',-- цех / объект
    facility      TEXT    NOT NULL DEFAULT '',-- установка / производство
    location      TEXT    NOT NULL DEFAULT '',-- дополнительное место
    constructions TEXT    NOT NULL DEFAULT '[]', -- JSON: [{kind, length, width, height}]
    isp_number    INTEGER,                    -- номер исполнительной схемы
    status        TEXT    NOT NULL DEFAULT 'new', -- new / done
    picture       TEXT,                       -- файл ситуационного плана
    file_path     TEXT,                       -- готовый DWG
    created_at    TEXT    NOT NULL,
    done_at       TEXT
);
"""

FIELDS = ("number", "date", "refinery", "department", "facility", "location",
          "constructions", "isp_number", "status", "picture", "file_path", "done_at")


def db_path() -> Path:
    return app_dir() / "tais.db"


def pictures_dir() -> Path:
    p = app_dir() / "pictures"
    p.mkdir(exist_ok=True)
    return p


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _row(r: sqlite3.Row | None) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    d["constructions"] = json.loads(d["constructions"] or "[]")
    return d


def list_acts(status: str | None = None) -> list[dict]:
    with _lock, _connect() as con:
        if status:
            rows = con.execute("SELECT * FROM acts WHERE status=? ORDER BY id", (status,))
        else:
            rows = con.execute("SELECT * FROM acts ORDER BY id DESC")
        return [_row(r) for r in rows.fetchall()]


def get_act(act_id: int) -> dict | None:
    with _lock, _connect() as con:
        return _row(con.execute("SELECT * FROM acts WHERE id=?", (act_id,)).fetchone())


def _values(data: dict) -> dict:
    out = {k: data[k] for k in FIELDS if k in data}
    if "constructions" in out:
        out["constructions"] = json.dumps(out["constructions"], ensure_ascii=False)
    return out


def create_act(data: dict) -> dict:
    vals = _values(data)
    vals["created_at"] = datetime.now().isoformat(timespec="seconds")
    cols = ", ".join(vals)
    marks = ", ".join("?" for _ in vals)
    with _lock, _connect() as con:
        cur = con.execute(f"INSERT INTO acts ({cols}) VALUES ({marks})", tuple(vals.values()))
        act_id = cur.lastrowid
    return get_act(act_id)


def update_act(act_id: int, data: dict) -> dict | None:
    vals = _values(data)
    if vals:
        sets = ", ".join(f"{k}=?" for k in vals)
        with _lock, _connect() as con:
            con.execute(f"UPDATE acts SET {sets} WHERE id=?", (*vals.values(), act_id))
    return get_act(act_id)


def delete_act(act_id: int) -> None:
    with _lock, _connect() as con:
        con.execute("DELETE FROM acts WHERE id=?", (act_id,))


def assign_isp_numbers(start: int) -> list[dict]:
    """Как в ORG_V5: актам без номера ИС — номера по порядку, начиная со start."""
    with _lock, _connect() as con:
        ids = [r["id"] for r in con.execute(
            "SELECT id FROM acts WHERE isp_number IS NULL ORDER BY id").fetchall()]
        for n, act_id in enumerate(ids):
            con.execute("UPDATE acts SET isp_number=? WHERE id=?", (start + n, act_id))
    return [get_act(i) for i in ids]
