import { useState } from 'react'
import { App, Button, Modal, Tooltip } from 'antd'
import { CheckCircleFilled, DesktopOutlined, FolderOpenOutlined, PrinterOutlined } from '@ant-design/icons'
import { api, desktop } from '../api.js'
import { showCadError } from './cadErrors.js'

// Печать готовой схемы и показ окна nanoCAD — общие для «Отработки» и «Генератора»
function useSchemeActions() {
  const { message, modal } = App.useApp()
  const [busy, setBusy] = useState(null) // 'show' | 'print' | 'print_close'

  const run = async (kind, fn, okText) => {
    setBusy(kind)
    try {
      const res = await fn()
      if (okText) message.success({ content: okText(res), duration: 10 })
      return res
    } catch (e) {
      showCadError(e, { modal, message })
      return null
    } finally {
      setBusy(null)
    }
  }
  // Итог печати — сообщением с путями файлов; проводник и PDF сами не открываются.
  // PDF-принтер печатает в файл в подпапке PDF (без окна «Сохранить как»).
  const printed = (path, closed) => (r) => {
    const sheets = r?.layouts?.length ? ` (листы ${r.layouts.join(', ')})` : ''
    let head = `Отправлено на печать${sheets}`
    if (r?.pdf?.length) {
      head = r.merged === false
        ? 'Листы сохранены отдельными PDF (для одного файла нужен пакет pypdf)'
        : `PDF сохранён${sheets}`
    }
    return (
      <div className="text-left">
        <div>{head}{closed ? '. Файл схемы сохранён и закрыт' : ''}</div>
        {r?.pdf?.map((p) => <div key={p} className="text-[12px] text-[#8e8e93] select-text">PDF: {p}</div>)}
        <div className="text-[12px] text-[#8e8e93] select-text">DWG: {r?.path || path}</div>
      </div>
    )
  }
  return {
    busy,
    show: (path) => run('show', () => api.cadShow(path)),
    print: (path) => run('print', () => api.cadPrint(path, false), printed(path, false)),
    printClose: (path) => run('print_close', () => api.cadPrint(path, true), printed(path, true)),
  }
}

// Кнопка «Печать» рядом с «Построить в nanoCAD»: неактивна, пока схема не построена
export function PrintButton({ file }) {
  const { busy, print } = useSchemeActions()
  const button = (
    <Button icon={<PrinterOutlined />} disabled={!file} loading={busy === 'print'} onClick={() => print(file.path)}>
      Печать
    </Button>
  )
  return (
    <Tooltip title={file ? `Распечатать ${file.name || file.path}` : 'Сначала постройте схему'}>
      {/* у неактивной кнопки подсказка не показывается без обёртки */}
      <span className="inline-block">{button}</span>
    </Tooltip>
  )
}

// Окно «Схема готова»: показать схему, распечатать, распечатать и сохранить (закрыть файл)
export function BuildDoneModal({ result, onClose }) {
  const { busy, show, print, printClose } = useSchemeActions()
  const path = result?.file?.path

  const doPrintClose = async () => {
    if (await printClose(path)) onClose()
  }

  return (
    <Modal open={!!result} onCancel={onClose} width={520} centered destroyOnHidden
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <Button color="default" variant="filled" icon={<DesktopOutlined />} loading={busy === 'show'}
            onClick={() => show(path)}>
            Показать схему
          </Button>
          <Button color="default" variant="filled" icon={<PrinterOutlined />} loading={busy === 'print'}
            onClick={() => print(path)}>
            Распечатать
          </Button>
          <Button color="green" variant="solid" icon={<PrinterOutlined />} loading={busy === 'print_close'}
            onClick={doPrintClose}>
            Распечатать и сохранить
          </Button>
        </div>
      }>
      {result && (
        <div className="flex flex-col items-center gap-2 pt-2 text-center">
          <CheckCircleFilled className="text-5xl !text-[#34c759]" />
          <div className="text-[17px] font-semibold">{result.title}</div>
          <div className="text-[#8e8e93]">{result.content}</div>
          {desktop && path && (
            <Button type="link" size="small" icon={<FolderOpenOutlined />} onClick={() => desktop.showItemInFolder(path)}>
              Показать в папке
            </Button>
          )}
          <div className="text-xs text-[#aeaeb2]">«Распечатать и сохранить» печатает листы и закрывает файл в nanoCAD с сохранением</div>
        </div>
      )}
    </Modal>
  )
}
