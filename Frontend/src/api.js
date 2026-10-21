// Обращения к локальному серверу TAIS. Ошибки сервера приходят как {code, message}.
export class ApiError extends Error {
  constructor(status, code, message) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function request(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  let data = null
  try {
    data = await res.json()
  } catch {
    data = null
  }
  if (!res.ok) {
    if (data?.code === 'demo_expired') window.dispatchEvent(new Event(DEMO_EVENT))
    const message = data?.message || (Array.isArray(data?.detail) ? 'Проверьте введённые значения' : `Ошибка ${res.status}`)
    throw new ApiError(res.status, data?.code || 'error', message)
  }
  return data
}

// срок демо-версии закончился посреди работы — шапка перепроверяет статус и закрывает программу
export const DEMO_EVENT = 'tais-demo-expired'

export const api = {
  health: () => request('GET', '/api/health'),
  demo: () => request('GET', '/api/demo'),
  getSettings: () => request('GET', '/api/settings'),
  saveSettings: (values) => request('PUT', '/api/settings', values),
  // схема из одной или нескольких конструкций: { constructions: [...] }
  scheme: (body) => request('POST', '/api/scheme', body),
  cadStatus: () => request('GET', '/api/cad/status'),
  elementsInfo: () => request('GET', '/api/elements'),
  clearGenPy: () => request('POST', '/api/cad/clear-gen-py'),
  cadBuild: (body) => request('POST', '/api/cad/build', body),
  // готовая схема: показать окно nanoCAD, распечатать (close — закрыть файл с сохранением)
  cadShow: (path) => request('POST', '/api/cad/show', { path }),
  cadPrint: (path, close = false) => request('POST', '/api/cad/print', { path, close }),
  cadPrinters: () => request('GET', '/api/cad/printers'),
  uploadElementsFile: (dataUrl) => request('PUT', '/api/elements-file', { data_url: dataUrl }),
  // акты
  acts: (status) => request('GET', status ? `/api/acts?status=${status}` : '/api/acts'),
  act: (id) => request('GET', `/api/acts/${id}`),
  createAct: (values) => request('POST', '/api/acts', values),
  updateAct: (id, values) => request('PUT', `/api/acts/${id}`, values),
  deleteAct: (id) => request('DELETE', `/api/acts/${id}`),
  setPicture: (id, dataUrl) => request('PUT', `/api/acts/${id}/picture`, { data_url: dataUrl }),
  pictureUrl: (id, version = '') => `/api/acts/${id}/picture?v=${version}`,
  assignIsp: (start) => request('POST', '/api/acts/isp-numbers', { start }),
  actPreview: (id) => request('GET', `/api/acts/${id}/preview`),
  buildAct: (id) => request('POST', `/api/acts/${id}/build`),
  reopenAct: (id) => request('POST', `/api/acts/${id}/reopen`),
  // аналитика и последний назначенный номер ИС
  stats: (days = 30) => request('GET', `/api/stats?days=${days}`),
  ispLast: () => request('GET', '/api/acts/isp-last'),
}

// Типы конструкций: русские подписи, английские коды
export const KIND_OPTIONS = [
  { value: 'auto', label: 'Автоматически' },
  { value: 'tower', label: 'Башенные' },
  { value: 'facade', label: 'Фасадные' },
  { value: 'widening', label: 'Уширение' },
  { value: 'balcony', label: 'Балкон (консольно-опорные)' },
  { value: 'radial', label: 'Радиальные' },
]
// пристраиваются к грани другой конструкции (или к уже стоящим лесам)
export const ATTACHABLE = ['widening', 'balcony']
export const kindLabel = (kind) => KIND_OPTIONS.find((o) => o.value === kind)?.label || kind

// Грани основной конструкции, к которым пристраивается уширение
export const SIDE_OPTIONS = [
  { value: 'y0', label: 'Передняя сторона' },
  { value: 'y1', label: 'Задняя сторона' },
  { value: 'x0', label: 'Левый торец' },
  { value: 'x1', label: 'Правый торец' },
]
export const sideLabel = (side) => SIDE_OPTIONS.find((o) => o.value === side)?.label || side

export const constructionText = (c) =>
  `${kindLabel(c.kind)} ${c.length}×${c.width}` +
  (c.kind === 'balcony' ? '' : `×${c.height}`) +
  (c.kind === 'radial' && c.widening ? ' + уширения' : '') +
  (ATTACHABLE.includes(c.kind) && c.attach_to > 0 ? ` → к №${c.attach_to}` : '')

// Возможности окна Electron (выбор папки, открыть файл). В обычном браузере их нет.
export const desktop = typeof window !== 'undefined' ? window.tais : undefined

// Флаги в шапке перечитывают состояние по этому событию (после сохранения настроек и т.п.)
export const STATUS_EVENT = 'tais:status'
export const notifyStatus = () => window.dispatchEvent(new Event(STATUS_EVENT))

// Аббревиатура для номера ИС — то же правило, что acts.abbreviate на сервере:
// «Цех №2» -> «Ц№2», «Цех каталитического крекинга» -> «ЦКК»; одно слово не меняется.
const SKIP_WORDS = new Set(['и', 'в', 'во', 'на', 'по', 'с', 'со', 'для', 'из', 'к', 'от', 'при'])
export function abbreviate(text) {
  const words = (text || '').split(/\s+/).filter(Boolean)
  if (words.length < 2) return (text || '').trim()
  let out = ''
  for (const w of words) {
    if (/\d/.test(w) || w.includes('№') || (w.length > 1 && w === w.toUpperCase() && w !== w.toLowerCase())) {
      out += w
    } else if (!SKIP_WORDS.has(w.toLowerCase())) {
      const letter = [...w].find((ch) => ch.toLowerCase() !== ch.toUpperCase())
      out += letter ? letter.toUpperCase() : ''
    }
  }
  return out
}

// Полный номер ИС (как acts.full_isp_number): пустые части пропускаются
export function ispNumber(values, settings) {
  if (!values?.isp_number) return null
  return [settings?.isp_prefix || 'П1-02', values.refinery, abbreviate(values.department),
    abbreviate(values.facility), `ИС${values.isp_number}`, settings?.year]
    .map((p) => (p == null ? '' : String(p).trim())).filter(Boolean).join('-')
}
