# Сборка установщика TAIS-Setup.exe
# Запуск из папки TAIS:  powershell -ExecutionPolicy Bypass -File build.ps1
# Нужны: Node.js (npm) и .venv с Python 3.10+ в папке TAIS.
#
# Демо-версия до даты (после неё программа не работает):
#   powershell -ExecutionPolicy Bypass -File build.ps1 -DemoUntil 2026-11-15
# Без -DemoUntil — полная версия.
param([string]$DemoUntil = "")
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

# Инструменты electron-builder (NSIS и др.) качаются с GitHub, который часто недоступен.
# Берём их с зеркала npmmirror; один раз скачанное лежит в %LOCALAPPDATA%\electron-builder\Cache.
if (-not $env:ELECTRON_BUILDER_BINARIES_MIRROR) {
    $env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"
}

# Встроенная библиотека: шаблон и спецификация входят в установщик
foreach ($f in @("Шаблон.dwg", "Веса элементов.csv")) {
    if (-not (Test-Path (Join-Path $root "Library\$f"))) { throw "Нет файла Library\$f" }
}

# Срок демо-версии вшивается в сервер (tais\_build_info.py, перезаписывается при каждой сборке)
$buildInfo = Join-Path $root "Backend\tais\_build_info.py"
if ($DemoUntil) {
    try { $d = [datetime]::ParseExact($DemoUntil, "yyyy-MM-dd", $null) }
    catch { throw "Дата демо-версии в формате ГГГГ-ММ-ДД, например 2026-11-15" }
    if ($d.Date -lt (Get-Date).Date) { throw "Дата демо-версии уже прошла: $DemoUntil" }
    Set-Content -Path $buildInfo -Encoding UTF8 -Value "DEMO_UNTIL = `"$DemoUntil`"  # создано build.ps1"
    Write-Host "Демо-версия до $DemoUntil" -ForegroundColor Cyan
} else {
    Set-Content -Path $buildInfo -Encoding UTF8 -Value "DEMO_UNTIL = None  # создано build.ps1: полная версия"
    Write-Host "Полная версия (без ограничения срока)" -ForegroundColor Cyan
}

function Step($title, $dir, [scriptblock]$body) {
    Write-Host "`n=== $title ===" -ForegroundColor Yellow
    Push-Location (Join-Path $root $dir)
    try {
        & $body
        if ($LASTEXITCODE -ne 0) { throw "Ошибка на шаге: $title" }
    } finally { Pop-Location }
}

Step "1/3 Интерфейс (Vite)" "Frontend" {
    npm install; if ($LASTEXITCODE -ne 0) { return }
    npm run build
}
Step "2/3 Сервер (PyInstaller)" "Backend" {
    & $python -m pip install -r requirements-dev.txt; if ($LASTEXITCODE -ne 0) { return }
    & $python -m unittest; if ($LASTEXITCODE -ne 0) { return }
    & $python -m PyInstaller tais-backend.spec --noconfirm
}
Step "3/3 Установщик (electron-builder)" "Desktop" {
    npm install; if ($LASTEXITCODE -ne 0) { return }
    # Electron скачивается отдельно (install.js); на чистой машине его может не оказаться
    if (-not (Test-Path "node_modules\electron\dist\electron.exe")) {
        Write-Host "Загрузка Electron..." -ForegroundColor Cyan
        node node_modules\electron\install.js; if ($LASTEXITCODE -ne 0) { return }
    }
    npm run dist
}
# дальше при разработке (python -m tais) — снова полная версия
Set-Content -Path $buildInfo -Encoding UTF8 -Value "DEMO_UNTIL = None  # создано build.ps1: полная версия"

if ($DemoUntil) {
    # чтобы не перепутать: демо-установщик называется иначе
    $setup = Get-ChildItem (Join-Path $root "Desktop\dist") -Filter "TAIS Setup *.exe" |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($setup) {
        $demoName = $setup.Name -replace "^TAIS Setup", "TAIS Demo до $DemoUntil Setup"
        Move-Item $setup.FullName (Join-Path $setup.DirectoryName $demoName) -Force
        Write-Host "Демо-установщик: Desktop\dist\$demoName" -ForegroundColor Green
    }
}
Write-Host "`nГотово: Desktop\dist\" -ForegroundColor Green
