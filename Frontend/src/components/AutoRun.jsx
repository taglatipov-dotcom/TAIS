import { useState } from 'react'
import { Alert, Button, Checkbox, Modal, Progress } from 'antd'
import { StopOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useBuild } from './BuildRunner.jsx'

// Настройки окна запуска запоминаются в этом браузере/окне TAIS
const TIP_KEY = 'tais.auto.pdfTipHidden'
const PRINT_KEY = 'tais.auto.print'
const read = (key, fallback) => {
  try {
    const v = localStorage.getItem(key)
    return v == null ? fallback : v === '1'
  } catch {
    return fallback
  }
}
const write = (key, value) => {
  try {
    localStorage.setItem(key, value ? '1' : '0')
  } catch {
    // без хранилища просто спросим снова
  }
}

// Встроенный PDF-принтер nanoCAD по умолчанию открывает каждый PDF в программе просмотра.
// Через COM эта настройка недоступна — её один раз выключает пользователь.
export function PdfViewerTip() {
  return (
    <Alert type="info" showIcon message="Отключите открытие PDF после печати"
      description={
        <>
          <div>Иначе nanoCAD откроет каждый напечатанный PDF в браузере или программе просмотра. Один раз в nanoCAD:</div>
          <ol className="m-0 mt-1 pl-5">
            <li>Файл → Печать (Ctrl+P).</li>
            <li>Принтер/плоттер — «Встроенный PDF-принтер» (Internal PDF-plotter).</li>
            <li>Кнопка «Свойства» рядом со списком принтеров.</li>
            <li>«Пользовательские свойства» (Custom Properties).</li>
            <li>Снимите галочку «Открыть в программе просмотра PDF по завершении»
              («Запускать программу просмотра PDF по умолчанию после печати»).</li>
            <li>OK — сохранить настройки.</li>
          </ol>
        </>
      } />
  )
}

// Кнопка «Авто» на странице «Отработка»: окно с пояснением, затем запуск всей очереди
export function AutoRunButton({ disabled, queueSize }) {
  const { startAuto } = useBuild()
  const [open, setOpen] = useState(false)
  const [print, setPrint] = useState(() => read(PRINT_KEY, true))
  const [tipDone, setTipDone] = useState(() => read(TIP_KEY, false))
  const [tipHidden, setTipHidden] = useState(() => read(TIP_KEY, false)) // отмечено в прошлый раз

  const start = () => {
    write(PRINT_KEY, print)
    write(TIP_KEY, tipDone)
    setOpen(false)
    startAuto({ print })
  }

  return (
    <>
      <Button color="green" variant="solid" icon={<ThunderboltOutlined />} disabled={disabled}
        onClick={() => { setTipHidden(read(TIP_KEY, false)); setOpen(true) }}>
        Авто
      </Button>
      <Modal open={open} onCancel={() => setOpen(false)} onOk={start} width={560} centered
        title="Авто-режим" okText={`Запустить (${queueSize})`} cancelText="Отмена">
        <div className="flex flex-col gap-3">
          <div>
            Все акты очереди ({queueSize}) строятся по порядку, без промежуточных окон. Окно nanoCAD
            на передний план не выводится — можно продолжать работу. Итог покажется одним окном в конце.
          </div>
          <Checkbox checked={print} onChange={(e) => setPrint(e.target.checked)}>
            Распечатать и сохранить каждую схему (файл закрывается в nanoCAD)
          </Checkbox>
          {print && !tipHidden && <PdfViewerTip />}
          {print && !tipHidden && (
            <Checkbox checked={tipDone} onChange={(e) => setTipDone(e.target.checked)}>
              Открытие PDF уже отключено — больше не напоминать
            </Checkbox>
          )}
        </div>
      </Modal>
    </>
  )
}

// Ход авто-режима: показывается на «Отработке», пока очередь строится
export function AutoProgress() {
  const { auto, stopAuto } = useBuild()
  if (!auto) return null
  const { index, total, current, stopping } = auto
  return (
    <Alert type="info" showIcon
      message={`Авто-режим: акт ${index + 1} из ${total} — № ${current.number} от ${current.date}`}
      description={
        <div className="flex flex-col gap-1">
          <Progress className="!m-0" percent={Math.round((index / total) * 100)} size="small" />
          <span className="text-[13px] text-[#8e8e93]">
            {stopping ? 'Остановка после текущего акта…' : 'Можно переключаться между экранами и работать в других программах.'}
          </span>
        </div>
      }
      action={
        <Button size="small" danger icon={<StopOutlined />} disabled={stopping} onClick={stopAuto}>Остановить</Button>
      } />
  )
}
