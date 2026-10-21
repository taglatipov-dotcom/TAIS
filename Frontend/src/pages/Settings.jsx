import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, App, Button, Card, Form, Input, InputNumber, Select, Space, Tooltip } from 'antd'
import { CheckCircleFilled, DeleteOutlined, EditOutlined, FolderOpenOutlined, PlusOutlined, PrinterOutlined, ReloadOutlined, UploadOutlined } from '@ant-design/icons'
import { api, desktop, notifyStatus } from '../api.js'
import { PdfViewerTip } from '../components/AutoRun.jsx'

function FolderInput({ value, onChange, placeholder }) {
  const pick = async () => {
    const dir = await desktop?.selectFolder(value)
    if (dir) onChange?.(dir)
  }
  return (
    <Space.Compact className="w-full">
      <Input value={value} onChange={(e) => onChange?.(e.target.value)} placeholder={placeholder} />
      {desktop && <Button icon={<FolderOpenOutlined />} onClick={pick}>Выбрать</Button>}
    </Space.Compact>
  )
}

// Зелёный флаг «добавлено» + путь и кнопка «Изменить»
function Added({ text, detail, action }) {
  return (
    <div className="flex items-center gap-3 rounded-xl bg-[#f7f7fa] px-3 py-2">
      <CheckCircleFilled className="text-lg !text-[#34c759]" />
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="font-medium text-[#248a3d]">{text}</span>
        {detail && <span className="truncate text-xs text-[#8e8e93]" title={detail}>{detail}</span>}
      </div>
      {action}
    </div>
  )
}

// Поле пути: пока не указано (или при первом запуске) — ввод, потом — зелёный флаг и «Изменить»
function PathField({ value, onChange, ok, okText, folder, placeholder, resetKey }) {
  const [editing, setEditing] = useState(!ok)
  useEffect(() => { setEditing(!ok) }, [ok, resetKey])
  if (!editing && ok) {
    return (
      <Added text={okText} detail={value}
        action={<Button size="small" color="default" variant="filled" icon={<EditOutlined />} onClick={() => setEditing(true)}>Изменить</Button>} />
    )
  }
  return folder
    ? <FolderInput value={value} onChange={onChange} placeholder={placeholder} />
    : <Input value={value} onChange={(e) => onChange?.(e.target.value)} placeholder={placeholder} />
}

export default function Settings() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [st, setSt] = useState(null)            // какие файлы на месте (как флаги в шапке)
  const [resetKey, setResetKey] = useState(0)    // после сохранения поля снова сворачиваются во флаги
  const [uploading, setUploading] = useState(false)
  const csvInput = useRef(null)
  const [printers, setPrinters] = useState(null) // { devices, template_device }
  const [loadingPrinters, setLoadingPrinters] = useState(false)
  const printer = Form.useWatch('printer', form)

  const loadPrinters = async () => {
    setLoadingPrinters(true)
    try {
      setPrinters(await api.cadPrinters())
    } catch (e) {
      message.error(e.message)
    } finally {
      setLoadingPrinters(false)
    }
  }

  const loadStatus = useCallback(() => api.cadStatus().then(setSt).catch(() => setSt(null)), [])

  useEffect(() => {
    api.getSettings().then((s) => form.setFieldsValue(s)).catch((e) => message.error(e.message))
    loadStatus()
  }, [form, message, loadStatus])

  // шаблона нет (ни встроенного, ни своего) — все пути показываем полями ввода
  const firstRun = !!st && !st.template_ok
  const okOr = (v) => (st && !firstRun ? v : false)

  const save = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      form.setFieldsValue(await api.saveSettings({ ...form.getFieldsValue(true), ...values }))
      message.success('Настройки сохранены')
      await loadStatus()
      setResetKey((k) => k + 1)
      notifyStatus()
    } catch (e) {
      message.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  // своя папка шаблона -> встроенная (пустой путь), сразу сохраняем
  const useBuiltin = async () => {
    form.setFieldValue('library_dir', '')
    await save()
  }

  const uploadCsv = (file) => {
    if (!file) return
    const reader = new FileReader()
    reader.onload = async () => {
      setUploading(true)
      try {
        await api.uploadElementsFile(reader.result)
        message.success('Файл спецификации загружен')
        await loadStatus()
        notifyStatus()
      } catch (e) {
        message.error(e.message)
      } finally {
        setUploading(false)
        if (csvInput.current) csvInput.current.value = ''
      }
    }
    reader.readAsDataURL(file)
  }

  const uploadButton = (label, small) => (
    <Tooltip title={st?.library_ok ? '' : 'Сначала укажите расположение файла шаблона и сохраните'}>
      <Button size={small ? 'small' : 'middle'} color="default" variant="filled"
        icon={small ? <EditOutlined /> : <UploadOutlined />} loading={uploading}
        disabled={!st?.library_ok} onClick={() => csvInput.current?.click()}>
        {label}
      </Button>
    </Tooltip>
  )

  return (
    <Form form={form} layout="vertical" requiredMark={false} className="mx-auto flex max-w-3xl flex-col gap-4">
      <h1 className="m-0 text-[28px] font-bold tracking-tight">Настройки</h1>
      {firstRun && (
        <Alert type="info" showIcon message="Шаблон не найден"
          description="Укажите расположение файла шаблона и путь сохранения схем, нажмите «Сохранить», затем загрузите файл спецификации." />
      )}
      <Card title="Файлы">
        <Form.Item name="library_dir" label="Расположение файла шаблона"
          extra={
            st?.library_ok && !firstRun
              ? (!st.library_builtin && st.builtin_library && (
                <Button type="link" size="small" className="!px-0" onClick={useBuiltin}>Вернуть встроенный шаблон</Button>
              ))
              : 'Папка, где лежит шаблон nanoCAD с блоками элементов.'
          }>
          <PathField folder ok={okOr(st?.library_ok)} okText={st?.library_builtin ? 'Встроенный шаблон' : 'Папка добавлена'}
            placeholder="C:\…\Library" resetKey={resetKey} />
        </Form.Item>
        <Form.Item name="template_name" label="Имя файла шаблона" rules={[{ required: true, message: 'Укажите имя файла' }]}
          extra={st && !st.template_ok && st.library_ok ? 'Файл с таким именем не найден в папке шаблона' : null}>
          <PathField ok={okOr(st?.template_ok)} okText="Файл добавлен" placeholder="Шаблон.dwg" resetKey={resetKey} />
        </Form.Item>
        <Form.Item name="output_dir" label="Путь сохранения схем"
          extra="Чертежи сохраняются в подпапку DWG, PDF — в подпапку PDF">
          <PathField folder ok={okOr(st?.output_ok)} okText="Путь добавлен" resetKey={resetKey} />
        </Form.Item>
        <Form.Item label="Файл спецификации загружен" className="!mb-0">
          {st?.spec_ok
            ? <Added text="Файл добавлен" detail={st.spec_file} action={uploadButton('Изменить', true)} />
            : (
              <div className="flex flex-wrap items-center gap-3 rounded-xl bg-[#fff5f4] px-3 py-2">
                <span className="flex-1 text-[13px] text-[#d70015]">
                  Загрузите «{st?.spec_expected || 'Веса элементов.csv'}» — без него известны веса только 13 элементов
                </span>
                {uploadButton('Загрузить файл')}
              </div>
            )}
          <input ref={csvInput} type="file" accept=".csv,text/csv" style={{ display: 'none' }}
            onChange={(e) => uploadCsv(e.target.files?.[0])} />
        </Form.Item>
      </Card>

      <Card title="Печать">
        <Form.Item label="Принтер" className="!mb-2"
          extra={
            (printer || printers?.template_device || '').toLowerCase().includes('pdf')
              ? 'PDF-принтер: листы сохраняются в PDF (подпапка PDF), без окна «Сохранить как»'
              : 'Листы A3 и A4 печатаются на этот принтер'
          }>
          <div className="flex gap-2">
            <Form.Item name="printer" noStyle>
              <Select className="flex-1" placeholder="Как в шаблоне"
                options={[
                  { value: '', label: `Как в шаблоне${printers?.template_device ? ` (${printers.template_device})` : ''}` },
                  ...(printers?.devices || []).map((d) => ({ value: d, label: d })),
                  ...(printer && !(printers?.devices || []).includes(printer) ? [{ value: printer, label: printer }] : []),
                ]} />
            </Form.Item>
            <Tooltip title="Получить список принтеров из nanoCAD (nanoCAD запустится, если не запущен)">
              <Button color="default" variant="filled" icon={printers ? <ReloadOutlined /> : <PrinterOutlined />}
                loading={loadingPrinters} onClick={loadPrinters}>
                {printers ? 'Обновить' : 'Список принтеров'}
              </Button>
            </Tooltip>
          </div>
        </Form.Item>
        <PdfViewerTip />
      </Card>

      <Card title="Основная надпись">
        <div className="grid grid-cols-2 gap-x-4">
          <Form.Item name="isp_prefix" label="Префикс номера ИС" extra="П1-02-Новойл-Ц№2-36-1-2-ИС2180-2026">
            <Input />
          </Form.Item>
          <Form.Item name="year" label="Год в номере ИС">
            <InputNumber min={2000} max={2100} className="w-full" />
          </Form.Item>
        </div>
        <div className="mb-2 text-[13px] text-[#8e8e93]">Заводы</div>
        <Form.List name="refineries">
          {(fields, { add, remove }) => (
            <div className="flex flex-col gap-2">
              {fields.map((f) => (
                <div key={f.key} className="flex gap-2">
                  <Form.Item name={[f.name, 'short']} className="!mb-0 w-40" rules={[{ required: true, message: 'Кратко' }]}>
                    <Input placeholder="Кратко: Новойл" />
                  </Form.Item>
                  <Form.Item name={[f.name, 'full']} className="!mb-0 flex-1" rules={[{ required: true, message: 'Полное имя' }]}>
                    <Input placeholder='Полное: ПАО АНК "Башнефть" "Башнефть-Новойл"' />
                  </Form.Item>
                  <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(f.name)} />
                </div>
              ))}
              <Button type="dashed" icon={<PlusOutlined />} onClick={() => add({ short: '', full: '' })}>Добавить завод</Button>
            </div>
          )}
        </Form.List>
      </Card>

      <div><Button type="primary" size="large" loading={saving} onClick={save}>Сохранить</Button></div>
    </Form>
  )
}
