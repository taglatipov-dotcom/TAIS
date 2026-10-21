// Мост между интерфейсом и Electron: только нужные функции, без доступа к Node.
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('tais', {
  selectFolder: (current) => ipcRenderer.invoke('select-folder', current),
  openPath: (p) => ipcRenderer.invoke('open-path', p),
  showItemInFolder: (p) => ipcRenderer.invoke('show-item', p),
  relaunch: () => ipcRenderer.invoke('relaunch'),
  // привлечь внимание (мигание в панели задач), если окно TAIS не в фокусе
  attention: () => ipcRenderer.invoke('attention'),
})
