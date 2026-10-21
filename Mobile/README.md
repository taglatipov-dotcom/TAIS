# TAIS — мобильное приложение (Android)

Упрощённый TAIS для телефона: вводите конструкции как в «Генераторе» — получаете
спецификацию с весами и три вида (спереди, сбоку, сверху). Работает без сети и без компьютера.
В настройках можно указать вес каждого элемента; веса хранятся на телефоне.

## Устройство
- Интерфейс: React + antd + Tailwind (как основной TAIS), Vite; в Android-приложение
  заворачивается Capacitor (`capacitor.config.json`, папка `android/` создаётся при первой сборке).
- Генератор — `src/generator/`: перенос `Backend/tais/generator` на JavaScript один в один
  (те же правила, тексты предупреждений, спецификация).
- Веса по умолчанию — из `Library/Веса элементов.csv` (встраиваются при сборке),
  свои веса — экран «Настройки» (`src/weights.js`).

## Сверка с Python-генератором
`tests/golden.json` — эталонные расчёты Python-генератора (30 схем: башенные, фасадные,
уширения, балконы, радиальные, ошибки). `npm test` сравнивает с ними JS-генератор.
После изменения правил в `Backend/tais/generator` (из корня проекта):

    .venv\Scripts\python Mobile\tools\make_golden.py
    cd Mobile && npm test

Если тест падает — перенести изменения правил в `src/generator/` (файлы названы как в Python).

## Сборка APK
1. Установить Android Studio и один раз открыть его (поставит Android SDK) и полный JDK 21
   (`winget install EclipseAdoptium.Temurin.21.JDK`): Java 25 из Android Studio и урезанная Java
   из PyCharm для Gradle 8.11 не годятся, скрипт сам выбирает подходящую.
2. `powershell -ExecutionPolicy Bypass -File build-android.ps1` в папке `Mobile`.
3. Скопировать `Mobile\TAIS-mobile.apk` на телефон и установить
   (разрешить установку из неизвестных источников).

Сеть: скрипт сам проверяет путь до dl.google.com (напрямую, системный прокси, порты VPN-клиентов),
при недоступности Maven Central берёт зеркала Aliyun (`gradle-mirrors.gradle`). Gradle можно положить
архивом `gradle-<версия>-all.zip` в эту папку. Свой прокси: `build-android.ps1 -Proxy 127.0.0.1:ПОРТ`.
Повторные сборки идут из кэша и почти не требуют сети.

Посмотреть в браузере без телефона: `npm install`, затем `npm run dev`.
