import { useEffect, useState } from 'react'
import { App, Tooltip } from 'antd'
import { useNavigate } from 'react-router-dom'
import { STATUS_EVENT, api } from '../api.js'
import { showCadError } from './cadErrors.js'

// Три флага в шапке: nanoCAD, файл шаблона, файл спецификации — зелёный/красный,
// при наведении подсказка, что сделать. Красный флаг кликабелен.
function Flag({ ok, label, tip, onClick }) {
  const cls = ok == null ? 'ios-flag-wait' : ok ? 'ios-flag-ok' : 'ios-flag-bad'
  return (
    <Tooltip title={tip} placement="bottomRight">
      <span className={`ios-flag ${cls}`} onClick={ok === false ? onClick : undefined}>
        <span className="dot" />
        <span className="flag-label">{label}</span>
      </span>
    </Tooltip>
  )
}

export default function StatusFlags() {
  const { modal, message } = App.useApp()
  const navigate = useNavigate()
  const [st, setSt] = useState(null)

  useEffect(() => {
    let alive = true
    const load = () => api.cadStatus().then((s) => alive && setSt(s)).catch(() => alive && setSt(null))
    load()
    const id = setInterval(load, 15000)
    window.addEventListener(STATUS_EVENT, load)
    return () => {
      alive = false
      clearInterval(id)
      window.removeEventListener(STATUS_EVENT, load)
    }
  }, [])

  const toSettings = () => navigate('/settings')

  if (!st) {
    return (
      <div className="flex items-center gap-2">
        <Flag label="nanoCAD" tip="Проверка…" />
        <Flag label="Файл шаблона" tip="Проверка…" />
        <Flag label="Файл спецификации" tip="Проверка…" />
      </div>
    )
  }

  let cad = { ok: true, tip: `nanoCAD ${st.version || ''} — ${st.running ? 'запущен' : 'установлен'}`, onClick: undefined }
  if (!st.platform_ok) {
    cad = { ok: false, tip: 'nanoCAD работает только в Windows', onClick: undefined }
  } else if (st.gen_py_error) {
    cad = { ok: false, tip: 'Ошибка кэша gen_py — нажмите, чтобы исправить',
      onClick: () => showCadError({ code: 'gen_py_cache', message: st.gen_py_error }, { modal, message }) }
  } else if (!st.installed) {
    cad = { ok: false, tip: 'Установите nanoCAD, чтобы строить схемы. Расчёт работает и без него.', onClick: undefined }
  }

  return (
    <div className="flex items-center gap-2">
      <Flag label="nanoCAD" ok={cad.ok} tip={cad.tip} onClick={cad.onClick} />
      <Flag label="Файл шаблона" ok={st.template_ok}
        tip={st.template_ok ? `Шаблон: ${st.template}` : 'Загрузите файл шаблона — укажите его расположение в настройках'}
        onClick={toSettings} />
      <Flag label="Файл спецификации" ok={st.spec_ok}
        tip={st.spec_ok ? `Спецификация: ${st.spec_file}` : `Загрузите файл спецификации «${st.spec_expected}» в настройках`}
        onClick={toSettings} />
    </div>
  )
}
