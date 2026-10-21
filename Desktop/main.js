// Оболочка TAIS: запускает локальный сервер (Python) и показывает интерфейс в окне.
const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const net = require('net')
const fs = require('fs')

let backend = null
let mainWindow = null

if (!app.requestSingleInstanceLock()) {
  app.quit()
}

// Свободный порт на 127.0.0.1
function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer()
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address()
      srv.close(() => resolve(port))
    })
    srv.on('error', reject)
  })
}

// Как запустить сервер: в сборке — tais-backend.exe, при разработке — python из .venv
// Встроенная библиотека (Шаблон.dwg, «Веса элементов.csv»): в сборке — resources\\library,
// при разработке — папка Library в корне проекта
function libraryDir() {
  return app.isPackaged
    ? path.join(process.resourcesPath, 'library')
    : path.resolve(__dirname, '..', 'Library')
}

function backendCommand(port) {
  const args = ['--port', String(port)]
  if (app.isPackaged) {
    const exe = path.join(process.resourcesPath, 'backend', 'tais-backend.exe')
    return { cmd: exe, args, cwd: path.dirname(exe) }
  }
  const root = path.resolve(__dirname, '..')
  const venvPython = path.join(root, '.venv', 'Scripts', 'python.exe')
  const python = fs.existsSync(venvPython) ? venvPython : 'python'
  return { cmd: python, args: ['-m', 'tais', ...args], cwd: path.join(root, 'Backend') }
}

// Отвечает ли адрес (для проверки, запущен ли Vite)
async function isReachable(url, timeoutMs = 1500) {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) })
    return res.ok
  } catch {
    return false
  }
}

async function waitForHealth(port, timeoutMs = 30000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/health`)
      if (res.ok) return true
    } catch {
      // сервер ещё стартует
    }
    await new Promise((r) => setTimeout(r, 300))
  }
  return false
}

function stopBackend() {
  if (backend && !backend.killed) {
    backend.kill()
  }
  backend = null
}

function launchBackend(port) {
  const { cmd, args, cwd } = backendCommand(port)
  backend = spawn(cmd, args, {
    cwd,
    windowsHide: true,
    env: { ...process.env, TAIS_LIBRARY_DIR: libraryDir() },
  })
  backend.stdout?.on('data', (d) => process.stdout.write(`[backend] ${d}`))
  backend.stderr?.on('data', (d) => process.stderr.write(`[backend] ${d}`))
  backend.on('exit', (code) => {
    if (mainWindow && code !== 0 && code !== null) {
      dialog.showErrorBox('TAIS', `Сервер TAIS неожиданно остановился (код ${code}). Подробности в %APPDATA%\\TAIS\\logs.`)
    }
  })
}

async function start() {
  // При разработке Vite проксирует /api на 8765 — используем этот порт;
  // если сервер уже запущен вручную, второй не запускаем.
  const devUrl = process.env.TAIS_DEV_URL
  const port = devUrl ? 8765 : await freePort()
  if (!(devUrl && (await waitForHealth(port, 500)))) {
    launchBackend(port)
  }

  const ok = await waitForHealth(port)
  if (!ok) {
    dialog.showErrorBox('TAIS', 'Не удалось запустить сервер TAIS. Подробности в %APPDATA%\\TAIS\\logs.')
    stopBackend()
    app.quit()
    return
  }

  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    title: 'TAIS',
    icon: path.join(__dirname, 'assets', 'icon.png'),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })
  // При разработке интерфейс берём с Vite (горячая перезагрузка), иначе — с сервера.
  // Если Vite не запущен — показываем собранный интерфейс с сервера, а не белый экран.
  let url = `http://127.0.0.1:${port}/`
  if (devUrl) {
    if (await isReachable(devUrl)) {
      url = devUrl
    } else {
      console.warn(`[TAIS] Vite не отвечает на ${devUrl} — открываю собранный интерфейс с сервера. ` +
        'Для горячей перезагрузки запустите: cd Frontend; npm run dev')
    }
  }
  mainWindow.loadURL(url)
  // Внешние ссылки открываем в обычном браузере
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
  // мигание в панели задач (авто-режим закончился) снимаем, когда пользователь вернулся в окно
  mainWindow.on('focus', () => mainWindow?.flashFrame(false))
  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

ipcMain.handle('select-folder', async (_e, current) => {
  const res = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    defaultPath: current || undefined,
  })
  return res.canceled ? null : res.filePaths[0]
})
ipcMain.handle('open-path', async (_e, p) => {
  if (p) {
    fs.mkdirSync(p, { recursive: true })
    return shell.openPath(p)
  }
  return null
})
// Перезапуск TAIS (например, после очистки кэша gen_py)
ipcMain.handle('relaunch', () => {
  stopBackend()
  app.relaunch()
  app.exit(0)
})
ipcMain.handle('attention', () => {
  if (mainWindow && !mainWindow.isFocused()) mainWindow.flashFrame(true)
})
ipcMain.handle('show-item', (_e, p) => {
  if (p) shell.showItemInFolder(p)
})

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.focus()
  }
})
app.whenReady().then(start)
app.on('window-all-closed', () => {
  stopBackend()
  app.quit()
})
app.on('before-quit', stopBackend)
