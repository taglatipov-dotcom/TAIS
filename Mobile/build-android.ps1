# Сборка Android-приложения TAIS (APK для установки на телефон).
# Нужно: Node.js 20+, Android Studio (в нём JDK 21 и Android SDK). Запуск из папки Mobile:
#   powershell -ExecutionPolicy Bypass -File build-android.ps1
# Готовый файл: Mobile\TAIS-mobile.apk
#
# Если GitHub и серверы Gradle/Google недоступны, скрипт сам переключается на зеркала
# (Gradle — Tencent, Maven — Aliyun). Можно и вручную: скачать браузером gradle-<версия>-bin.zip
# или -all.zip и положить в папку Mobile — тогда Gradle возьмётся из этого файла.
#
# Сеть (если загрузка обрывается по таймауту):
#   -Proxy 127.0.0.1:12334   — свой прокси (например, порт Hiddify/другого VPN-клиента)
#   -Direct                  — без системного прокси Windows, напрямую
param(
    [string]$Proxy = '',
    [switch]$Direct
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Run($what, [scriptblock]$cmd) {
    Write-Host "==> $what" -ForegroundColor Cyan
    & $cmd
    if ($LASTEXITCODE -ne 0) { throw "Не удалось: $what (код $LASTEXITCODE)" }
}

# JDK для Gradle 8.11 (Capacitor 7): Java 17…23. Java 25 из новых Android Studio Gradle не поддерживает,
# поэтому ищем подходящую среди установленных: Android Studio, IDE JetBrains (папка jbr), JDK в Program Files.
function Get-JavaMajor($home_) {
    $rel = Join-Path $home_ 'release'
    if (-not (Test-Path $rel)) { return 0 }
    $line = Select-String -Path $rel -Pattern '^JAVA_VERSION="(\d+)' | Select-Object -First 1
    if ($line) { return [int]$line.Matches[0].Groups[1].Value } else { return 0 }
}
$candidates = @()
if ($env:JAVA_HOME) { $candidates += $env:JAVA_HOME }
$candidates += Join-Path $env:ProgramFiles 'Android\Android Studio\jbr'
foreach ($root in @((Join-Path $env:ProgramFiles 'JetBrains'), (Join-Path $env:LOCALAPPDATA 'Programs'))) {
    if (Test-Path $root) { Get-ChildItem $root -Directory | ForEach-Object { $candidates += Join-Path $_.FullName 'jbr' } }
}
foreach ($root in @((Join-Path $env:ProgramFiles 'Java'), (Join-Path $env:ProgramFiles 'Eclipse Adoptium'),
                    (Join-Path $env:ProgramFiles 'Microsoft'), (Join-Path $env:USERPROFILE '.jdks'))) {
    if (Test-Path $root) { Get-ChildItem $root -Directory | ForEach-Object { $candidates += $_.FullName } }
}
# нужен полный JDK: с jlink (урезанная Java внутри PyCharm без него не годится)
$jdk = $candidates | Where-Object { (Test-Path (Join-Path $_ 'bin\java.exe')) -and (Test-Path (Join-Path $_ 'bin\jlink.exe')) } |
    ForEach-Object { [pscustomobject]@{ Path = $_; Major = (Get-JavaMajor $_) } } |
    Where-Object { $_.Major -ge 17 -and $_.Major -le 23 } |
    Sort-Object Major -Descending | Select-Object -First 1
if (-not $jdk) {
    throw ('Не найден полный JDK 17…23 (с jlink). Установите JDK 21 и запустите скрипт снова: ' +
           'winget install EclipseAdoptium.Temurin.21.JDK  (или установщик с adoptium.net)')
}
$env:JAVA_HOME = $jdk.Path
Write-Host "Java $($jdk.Major): $($jdk.Path)" -ForegroundColor Green
if (-not $env:ANDROID_HOME) {
    $sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
    if (Test-Path $sdk) { $env:ANDROID_HOME = $sdk } else { throw 'Не найден Android SDK: откройте Android Studio один раз (SDK ставится при первом запуске)' }
}

Run 'Установка пакетов' { npm install }
Run 'Проверка генератора (сверка с Python)' { npm test }
Run 'Сборка интерфейса' { npm run build }
if (-not (Test-Path 'android')) {
    Run 'Создание Android-проекта' { npx cap add android }
}
# Иконки приложения (заранее нарисованы из логотипа: assets/android-res)
Copy-Item 'assets\android-res\*' 'android\app\src\main\res' -Recurse -Force
Run 'Копирование интерфейса в Android-проект' { npx cap sync android }
# --- Сеть для Gradle: сначала проверяем, каким путём сервер Google вообще отвечает ---
# (curl.exe есть в Windows 10/11). Пробуем: свой -Proxy, напрямую, системный прокси Windows,
# частые порты VPN-клиентов (Hiddify 12334/2334, v2rayN 10808/10809, Clash 7890).
$probe = 'https://dl.google.com/dl/android/maven2/com/android/tools/build/gradle/8.7.2/gradle-8.7.2.pom'
function Test-Route($proxy) {
    $args_ = @('-s', '-o', 'NUL', '-w', '%{http_code}', '--max-time', '20')
    if ($proxy) { $args_ += @('-x', "http://$proxy") } else { $args_ += @('--noproxy', '*') }
    $code = & curl.exe @args_ $probe
    return ($code -eq '200')
}
$routes = @()
if ($Proxy) { $routes += $Proxy }
else {
    if (-not $Direct) {
        $is = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
        if ($is -and $is.ProxyEnable -eq 1 -and $is.ProxyServer) {
            $sp = $is.ProxyServer
            if ($sp -match 'https=([^;]+)') { $sp = $Matches[1] } elseif ($sp -match 'http=([^;]+)') { $sp = $Matches[1] }
            $routes += ($sp -replace '^\w+://', '')
        }
    }
    $routes += ''                       # напрямую
    if (-not $Direct) { $routes += '127.0.0.1:12334', '127.0.0.1:2334', '127.0.0.1:10809', '127.0.0.1:10808', '127.0.0.1:7890' }
}
$route = $null
foreach ($r in ($routes | Select-Object -Unique)) {
    $label = if ($r) { "прокси $r" } else { 'напрямую' }
    Write-Host "Проверка связи с dl.google.com: $label ... " -NoNewline
    if (Test-Route $r) { Write-Host 'есть' -ForegroundColor Green; $route = $r; break }
    Write-Host 'нет' -ForegroundColor Yellow
}
if ($null -eq $route) {
    throw ("Сервер Google (dl.google.com) не отвечает ни напрямую, ни через прокси. Gradle без него не соберёт APK. " +
           "Включите VPN (в Hiddify — режим VPN/TUN) или узнайте порт прокси и запустите: build-android.ps1 -Proxy 127.0.0.1:ПОРТ")
}
$net = @(
    '-Dorg.gradle.internal.http.connectionTimeout=60000',
    '-Dorg.gradle.internal.http.socketTimeout=60000',
    '-Dorg.gradle.internal.repository.max.retries=5',
    '-Dorg.gradle.internal.repository.initial.backoff=2000'
)
if ($route) {
    $ph, $pp = $route.Split(':')
    $net += "-Dhttp.proxyHost=$ph", "-Dhttp.proxyPort=$pp", "-Dhttps.proxyHost=$ph", "-Dhttps.proxyPort=$pp"
}
$env:GRADLE_OPTS = ($net -join ' ')

# --- Gradle: версия из обёртки, архив -bin (меньше), таймаут побольше, источник с запасом ---
$props = Join-Path $PSScriptRoot 'android\gradle\wrapper\gradle-wrapper.properties'
$text = Get-Content $props -Raw
if ($text -notmatch 'gradle-([\d.]+)-(?:all|bin)\.zip') { throw "Не найдена версия Gradle в $props" }
$gv = $Matches[1]
$zipName = "gradle-$gv-bin.zip"
$sources = @()
# архив, скачанный вручную в папку Mobile (подходит и -bin, и -all)
$found = Get-ChildItem -Path $PSScriptRoot -Filter "gradle-$gv-*.zip" -File -ErrorAction SilentlyContinue
foreach ($f in $found) {
    Write-Host "Найден архив Gradle: $($f.FullName)" -ForegroundColor Green
    $sources += 'file:///' + ($f.FullName -replace '\\', '/')
}
if (-not $found) { Write-Host "Архив gradle-$gv-*.zip в папке $PSScriptRoot не найден — загрузка из сети" -ForegroundColor Yellow }
$sources += "https://services.gradle.org/distributions/$zipName"
$sources += "https://mirrors.cloud.tencent.com/gradle/$zipName"

function Set-GradleSource($url) {
    $t = Get-Content $props -Raw
    $t = $t -replace '(?m)^distributionUrl=.*$', ('distributionUrl=' + ($url -replace ':', '\:'))
    if ($t -match '(?m)^networkTimeout=') { $t = $t -replace '(?m)^networkTimeout=.*$', 'networkTimeout=120000' }
    else { $t = $t.TrimEnd() + "`r`nnetworkTimeout=120000`r`n" }
    [IO.File]::WriteAllText($props, $t)
}

Push-Location android
try {
    $ok = $false
    foreach ($src in $sources) {
        Write-Host "==> Gradle $gv : $src" -ForegroundColor Cyan
        Set-GradleSource $src
        & .\gradlew.bat --version @net
        if ($LASTEXITCODE -eq 0) { $ok = $true; break }
        Write-Host 'Не удалось загрузить Gradle из этого источника, пробую следующий' -ForegroundColor Yellow
    }
    if (-not $ok) {
        throw "Gradle не загрузился. Скачайте браузером $zipName (например, https://mirrors.cloud.tencent.com/gradle/$zipName) и положите в папку Mobile, затем запустите скрипт снова."
    }

    & .\gradlew.bat --stop | Out-Null
    # --- Сборка: сначала обычные репозитории, при неудаче — зеркала Aliyun ---
    Write-Host '==> Сборка APK' -ForegroundColor Cyan
    & .\gradlew.bat assembleDebug @net
    if ($LASTEXITCODE -ne 0) {
        Write-Host '==> Сборка APK через зеркала Maven (Aliyun)' -ForegroundColor Cyan
        & .\gradlew.bat assembleDebug --init-script ..\gradle-mirrors.gradle @net
        if ($LASTEXITCODE -ne 0) {
            throw ("Не удалось: Сборка APK (код $LASTEXITCODE). Если выше 'Read timed out' / 'Connect timed out' — " +
                   "Gradle не может скачать библиотеки. Запустите снова: с VPN-прокси " +
                   "'build-android.ps1 -Proxy 127.0.0.1:ПОРТ' или напрямую 'build-android.ps1 -Direct'. " +
                   "Уже скачанное сохраняется, повторный запуск продолжит с места остановки.")
        }
    }
} finally { Pop-Location }

Copy-Item 'android\app\build\outputs\apk\debug\app-debug.apk' 'TAIS-mobile.apk' -Force
Write-Host "Готово: $(Join-Path $PSScriptRoot 'TAIS-mobile.apk')" -ForegroundColor Green
