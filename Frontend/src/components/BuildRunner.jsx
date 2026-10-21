import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { Alert, App, Button, Modal } from 'antd'
import { CheckCircleFilled, ExclamationCircleFilled, FolderOpenOutlined } from '@ant-design/icons'
import { api, desktop } from '../api.js'
import { BuildDoneModal } from './SchemeActions.jsx'
import { missingText, showCadError, specText } from './cadErrors.js'

// Построение схем в nanoCAD живёт выше страниц (в App.jsx), а не внутри «Отработки» или «Генератора»:
// если во время построения перейти на другой экран, результат и окно «Схема готова» не теряются.
// Здесь же — авто-режим: все акты очереди по порядку, одно итоговое окно в конце.

// Сколько актов отработано за этот запуск программы. Прогресс считаем по ним, а не по всем
// актам «Готово» за всё время: иначе при одном оставшемся акте полоска стояла на половине.
const SESSION_KEY = 'tais.work.built'
export function readBuilt() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY) || '[]')
  } catch {
    return []
  }
}
function rememberBuilt(id) {
  const ids = [...new Set([...readBuilt(), id])]
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(ids))
  } catch {
    // без хранилища прогресс просто начнётся заново
  }
}

// После этих ошибок остальные акты тоже не построятся — авто-режим останавливается
const FATAL = ['nanocad_not_installed', 'nanocad_unsupported_os', 'template_missing', 'gen_py_cache', 'demo_expired']

const BuildContext = createContext(null)
export const useBuild = () => useContext(BuildContext)

export function BuildProvider({ children }) {
  const { message, modal } = App.useApp()
  const [busy, setBusy] = useState(null)          // { kind: 'act', id } | { kind: 'generator' } | { kind: 'auto' }
  const [done, setDone] = useState(null)          // окно «Схема готова»
  const [lastFiles, setLastFiles] = useState({})  // { work, generator } — для кнопки «Печать»
  const [version, setVersion] = useState(0)       // растёт после каждого построенного акта — «Отработка» перечитывает очередь
  const [auto, setAuto] = useState(null)          // ход авто-режима: { index, total, current, stopping }
  const [autoDone, setAutoDone] = useState(null)  // итоговое окно авто-режима
  const lock = useRef(false)                      // nanoCAD строит по одной схеме
  const stopRef = useRef(false)

  const acquire = (kind) => {
    if (lock.current) {
      message.warning('nanoCAD сейчас занят построением другой схемы')
      return false
    }
    lock.current = true
    setBusy(kind)
    return true
  }
  const release = () => {
    lock.current = false
    setBusy(null)
  }

  const buildAct = useCallback(async (id) => {
    if (!acquire({ kind: 'act', id })) return
    try {
      const res = await api.buildAct(id)
      const file = { path: res.file.path, name: res.act.isp_full }
      rememberBuilt(id)
      setLastFiles((f) => ({ ...f, work: file }))
      setDone({
        file,
        title: `Схема ${res.act.isp_full} готова`,
        content: `Элементов: ${res.file.inserted}. Надписей заполнено: ${res.file.texts}.${missingText(res.file)}${specText(res.file)}`,
      })
      setVersion((v) => v + 1)
    } catch (e) {
      showCadError(e, { modal, message })
    } finally {
      release()
    }
  }, [message, modal]) // eslint-disable-line react-hooks/exhaustive-deps

  const buildScheme = useCallback(async (values) => {
    if (!acquire({ kind: 'generator' })) return
    try {
      const res = await api.cadBuild(values)
      const file = { path: res.file.path }
      setLastFiles((f) => ({ ...f, generator: file }))
      setDone({
        file,
        title: 'Чертёж сформирован',
        content: `Вставлено элементов: ${res.file.inserted}. Файл: ${res.file.path}.${missingText(res.file)}${specText(res.file)}`,
      })
    } catch (e) {
      showCadError(e, { modal, message })
    } finally {
      release()
    }
  }, [message, modal]) // eslint-disable-line react-hooks/exhaustive-deps

  // Авто-режим: каждый акт очереди — построить, затем (print) распечатать и закрыть с сохранением.
  // Окно nanoCAD на передний план не выводится, PDF рядом с DWG; итог — одним окном в конце.
  const startAuto = useCallback(async ({ print }) => {
    if (!acquire({ kind: 'auto' })) return
    stopRef.current = false
    let queue = []
    try {
      queue = await api.acts('new')
    } catch (e) {
      message.error(e.message)
      release()
      return
    }
    if (!queue.length) {
      message.info('Очередь пуста')
      release()
      return
    }
    const results = []
    let fatal = null
    for (let i = 0; i < queue.length; i++) {
      if (stopRef.current) break
      const a = queue[i]
      setAuto((s) => ({ stopping: s?.stopping || false, index: i, total: queue.length, current: a }))
      const r = { id: a.id, number: a.number, date: a.date, isp: a.isp_full }
      try {
        const res = await api.buildAct(a.id)
        r.isp = res.act.isp_full
        r.dwg = res.file.path
        r.notes = `${missingText(res.file)}${res.file.spec && !res.file.spec.ok ? specText(res.file) : ''}`.trim()
        rememberBuilt(a.id)
        setVersion((v) => v + 1)
        if (print) {
          try {
            const p = await api.cadPrint(res.file.path, true)
            r.pdf = p.pdf || []
            r.device = p.device
            r.closed = p.closed
          } catch (e) {
            r.printError = e.message
          }
        }
      } catch (e) {
        r.error = e.message
        if (FATAL.includes(e.code)) fatal = e
      }
      results.push(r)
      if (fatal) break
    }
    const stopped = stopRef.current && results.length < queue.length
    setAuto(null)
    release()
    setAutoDone({ results, total: queue.length, stopped, fatal: fatal?.message, print })
    desktop?.attention?.()  // окно TAIS мигает в панели задач, если пользователь в другой программе
    if (fatal?.code === 'gen_py_cache') showCadError(fatal, { modal, message })
  }, [message, modal]) // eslint-disable-line react-hooks/exhaustive-deps

  const stopAuto = useCallback(() => {
    stopRef.current = true
    setAuto((s) => (s ? { ...s, stopping: true } : s))
  }, [])

  const value = useMemo(() => ({
    busy, lastFiles, version, auto, buildAct, buildScheme, startAuto, stopAuto,
  }), [busy, lastFiles, version, auto, buildAct, buildScheme, startAuto, stopAuto])

  return (
    <BuildContext.Provider value={value}>
      {children}
      <BuildDoneModal result={done} onClose={() => setDone(null)} />
      <AutoDoneModal result={autoDone} onClose={() => setAutoDone(null)} />
    </BuildContext.Provider>
  )
}

function PathLine({ label, path }) {
  return (
    <div className="flex gap-1.5 text-[13px]">
      <span className="shrink-0 text-[#8e8e93]">{label}:</span>
      <span className="break-all select-text">{path}</span>
    </div>
  )
}

// Итог авто-режима: что построено, где лежат DWG и PDF, что не получилось
function AutoDoneModal({ result, onClose }) {
  if (!result) return null
  const { results, total, stopped, fatal, print } = result
  const ok = results.filter((r) => !r.error)
  const failed = results.length - ok.length
  const printFailed = ok.filter((r) => r.printError).length
  const allGood = !failed && !printFailed && !stopped && results.length === total
  const title = stopped ? 'Авто-режим остановлен' : fatal ? 'Авто-режим прерван' : 'Авто-режим завершён'

  const openFolder = () => api.getSettings().then((s) => desktop.openPath(s.output_dir)).catch(() => {})

  return (
    <Modal open onCancel={onClose} width={640} centered
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          {desktop && (
            <Button color="default" variant="filled" icon={<FolderOpenOutlined />} onClick={openFolder}>
              Папка чертежей
            </Button>
          )}
          <Button type="primary" onClick={onClose}>Готово</Button>
        </div>
      }>
      <div className="flex flex-col items-center gap-1 pt-2 text-center">
        {allGood
          ? <CheckCircleFilled className="text-5xl !text-[#34c759]" />
          : <ExclamationCircleFilled className="text-5xl !text-[#ff9500]" />}
        <div className="text-[17px] font-semibold">{title}</div>
        <div className="text-[#8e8e93]">
          Построено схем: {ok.length} из {total}
          {failed ? ` · с ошибкой: ${failed}` : ''}
          {printFailed ? ` · не распечатано: ${printFailed}` : ''}
        </div>
      </div>
      {fatal && <Alert className="!mt-3" type="error" showIcon message={fatal} />}
      <div className="mt-3 flex max-h-[50vh] flex-col gap-2 overflow-y-auto">
        {results.map((r) => (
          <div key={r.id} className="rounded-[10px] bg-[#f7f7fa] px-3 py-2 text-left">
            <div className="text-[14px] font-semibold">
              Акт № {r.number} от {r.date}{r.isp ? ` — ${r.isp}` : ''}
            </div>
            {r.error && <div className="text-[13px] text-[#ff3b30]">Не построен: {r.error}</div>}
            {r.dwg && <PathLine label="DWG" path={r.dwg} />}
            {r.pdf?.map((p) => <PathLine key={p} label="PDF" path={p} />)}
            {r.dwg && print && !r.printError && !r.pdf?.length && (
              <div className="text-[13px] text-[#8e8e93]">Отправлено на принтер {r.device}</div>
            )}
            {r.printError && <div className="text-[13px] text-[#ff3b30]">Не распечатан: {r.printError}</div>}
            {r.notes && <div className="text-[12px] text-[#8e8e93]">{r.notes}</div>}
          </div>
        ))}
      </div>
      {print && ok.length > 0 && (
        <div className="mt-2 text-center text-xs text-[#aeaeb2]">Построенные схемы распечатаны, сохранены и закрыты в nanoCAD</div>
      )}
    </Modal>
  )
}
