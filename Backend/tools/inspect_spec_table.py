"""Разведка таблицы спецификации в nanoCAD.

Как запустить (Windows):
  1. Откройте в nanoCAD файл Шаблон.dwg (или любую готовую схему).
  2. В папке TAIS\\Backend выполните:
         ..\\.venv\\Scripts\\python tools\\inspect_spec_table.py
  3. Пришлите файл table_report.txt, который появится рядом со скриптом.

Скрипт ничего не меняет в чертеже — только читает.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

REPORT = Path(__file__).with_name("table_report.txt")
lines: list[str] = []


def say(text: str = "") -> None:
    print(text)
    lines.append(text)


def members(obj) -> list[str]:
    out = []
    ti = obj._oleobj_.GetTypeInfo()
    attr = ti.GetTypeAttr()
    for i in range(attr.cFuncs):
        fd = ti.GetFuncDesc(i)
        names = ti.GetNames(fd.memid)
        kind = {1: "метод", 2: "чтение", 4: "запись", 8: "запись"}.get(fd.invkind, str(fd.invkind))
        out.append(f"{names[0]}({', '.join(names[1:])})  [{kind}]")
    return sorted(set(out))


def try_call(obj, name, *args):
    try:
        attr = getattr(obj, name)
        val = attr(*args) if callable(attr) else attr
        return f"{name}{args} = {val!r}"
    except Exception as exc:
        return f"{name}{args} -> ошибка: {exc}"


def main() -> None:
    import win32com.client
    import win32com.client.dynamic

    app = win32com.client.GetActiveObject("nanoCAD.Application")
    doc = app.ActiveDocument
    say(f"nanoCAD {app.Version}, документ: {doc.Name}")
    for k in range(doc.Layouts.Count):
        lay = doc.Layouts.Item(k)
        block = lay.Block
        kinds = {}
        for i in range(block.Count):
            ent = block.Item(i)
            kinds[ent.ObjectName] = kinds.get(ent.ObjectName, 0) + 1
        say(f"\nЛист «{lay.Name}»: {block.Count} объектов: {kinds}")

        for i in range(block.Count):
            ent = block.Item(i)
            name = ent.ObjectName or ""
            if "table" not in name.lower():
                continue
            say(f"\n=== Таблица на листе «{lay.Name}», объект {i}: {name}")
            t = win32com.client.dynamic.Dispatch(ent._oleobj_)
            try:
                say("Методы и свойства:")
                for m in members(ent):
                    say("   " + m)
            except Exception as exc:
                say(f"   описания типа нет: {exc}")
            say("Пробы:")
            for prop in ("Rows", "Columns", "RowCount", "ColumnCount", "InsertionPoint",
                         "Height", "Width", "StyleName"):
                say("   " + try_call(t, prop))
            for r in range(0, 4):
                for c in range(0, 4):
                    for fn in ("GetText", "GetCellText", "GetCellValue"):
                        res = try_call(t, fn, r, c)
                        if "ошибка" not in res:
                            say("   " + res)
                            break
                    else:
                        say(f"   ячейка ({r},{c}): ни один способ чтения не сработал")
            for fn in ("GetRowHeight", "GetColumnWidth"):
                say("   " + try_call(t, fn, 1))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        say("ОШИБКА:\n" + traceback.format_exc())
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nОтчёт сохранён: {REPORT}")
    if sys.stdin.isatty():
        input("Нажмите Enter, чтобы закрыть…")
