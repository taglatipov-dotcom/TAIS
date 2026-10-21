"""Запуск сервера:  python -m tais --port 8765"""
from __future__ import annotations

import argparse
import logging
import sys


def main() -> None:
    parser = argparse.ArgumentParser(prog="tais")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    from .settings import app_dir

    log_dir = app_dir() / "logs"
    log_dir.mkdir(exist_ok=True)
    handlers = [logging.FileHandler(log_dir / "backend.log", encoding="utf-8")]
    if sys.stderr is not None:  # в сборке без консоли stderr нет
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    import uvicorn
    from .app import app

    uvicorn.run(app, host=args.host, port=args.port, log_config=None)


if __name__ == "__main__":
    main()
