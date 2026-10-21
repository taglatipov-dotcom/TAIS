# PyInstaller: собирает Backend в папку dist/tais-backend (запуск: tais-backend.exe --port N)
# Сборка:  .venv\Scripts\python -m PyInstaller tais-backend.spec --noconfirm
block_cipher = None

a = Analysis(
    ["run_backend.py"],
    pathex=["."],
    datas=[("tais/static", "tais/static")],
    hiddenimports=["tais._build_info", "win32com", "win32com.client", "pythoncom", "pywintypes", "win32gui", "win32con"],
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="tais-backend",
          console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="tais-backend", upx=False)
