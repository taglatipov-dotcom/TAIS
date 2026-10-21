import { useEffect, useMemo, useState } from 'react'
import { Alert, App, Button, Card, Descriptions, Form, Input, InputNumber, Select } from 'antd'
import { HistoryOutlined, RedoOutlined } from '@ant-design/icons'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { abbreviate, api, ispNumber } from '../api.js'
import ConstructionsList, { NEW_CONSTRUCTION } from '../components/ConstructionsList.jsx'
import PicturePaste from '../components/PicturePaste.jsx'

const EMPTY = {
  number: '', date: '', refinery: undefined, department: '', facility: '', location: '',
  isp_number: null, constructions: [{ ...NEW_CONSTRUCTION }],
}

const DATE_RE = /^\d{2}\.\d{2}\.\d{4}$/

// Подсказка под цехом/установкой: что пойдёт в номер ИС, если указано несколько слов
function AbbrHint({ value }) {
  const short = abbreviate(value)
  if (!value || short === value.trim()) return null
  return <span>В номере ИС: <b>{short}</b></span>
}

// Предпросмотр основной надписи — то же, что программа впишет в шаблон
function TitlePreview({ values, settings }) {
  const ref = settings?.refineries?.find((r) => r.short === values.refinery)
  const isp = ispNumber(values, settings) || 'назначается позже'
  const location = [values.department, values.facility, values.location].filter((v) => v && v.trim()).map((v) => `${v.trim()}. `).join('')
  return (
    <Descriptions size="small" column={1} bordered title="Основная надпись">
      <Descriptions.Item label="Номер ИС">{isp}</Descriptions.Item>
      <Descriptions.Item label="Акт">№{values.number || '…'} от {values.date || '…'}</Descriptions.Item>
      <Descriptions.Item label="Завод">{ref?.full || values.refinery || '…'}</Descriptions.Item>
      <Descriptions.Item label="Место">{location || '…'}</Descriptions.Item>
    </Descriptions>
  )
}

export default function ActEdit() {
  const { id } = useParams()
  const isNew = !id
  const navigate = useNavigate()
  const location = useLocation()
  const { message, modal } = App.useApp()
  const [form] = Form.useForm()
  const values = Form.useWatch([], form) || EMPTY
  const [settings, setSettings] = useState(null)
  const [picture, setPicture] = useState(null) // data URL новой картинки
  const [pictureSrc, setPictureSrc] = useState(null)
  const [pictureError, setPictureError] = useState(false)
  const [prevAct, setPrevAct] = useState(null) // «Предыдущий акт» после «Сохранить акт и продолжить»
  const [status, setStatus] = useState('new') // 'done' — схема по акту уже построена
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.getSettings().then(setSettings).catch((e) => message.error(e.message))
  }, [message])

  useEffect(() => {
    setPicture(null)
    setPictureError(false)
    if (isNew) {
      // переход сюда из «Сохранить акт и продолжить» на существующем акте — поля переносятся
      form.setFieldsValue({ ...EMPTY, ...(location.state?.keep || {}) })
      setPrevAct(location.state?.prev || null)
      setStatus('new')
      setPictureSrc(null)
      return
    }
    setPrevAct(null)
    api.act(id).then((a) => {
      form.setFieldsValue(a)
      setStatus(a.status)
      setPictureSrc(a.has_picture ? api.pictureUrl(a.id, Date.now()) : null)
    }).catch((e) => message.error(e.message))
    // location.state читаем только при смене акта
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, isNew, form, message])

  const refineryOptions = useMemo(
    () => (settings?.refineries || []).map((r) => ({ value: r.short, label: r.short, title: r.full })),
    [settings],
  )

  const onPicture = (dataUrl) => {
    setPicture(dataUrl)
    setPictureError(false)
  }

  // Готовый акт изменили — спросить, вернуть ли его в очередь, чтобы схему построить заново
  const askRedo = () => new Promise((resolve) => {
    modal.confirm({
      title: 'Переделать схему?',
      content: 'По этому акту схема уже построена. Вернуть акт в очередь «В работе», чтобы построить схему заново с изменениями?',
      okText: 'Переделать',
      cancelText: 'Только сохранить',
      onOk: () => resolve(true),
      onCancel: () => resolve(false),
    })
  })

  // Вернуть готовый акт в очередь без изменений
  const redo = async () => {
    try {
      await api.reopenAct(id)
      setStatus('new')
      message.success('Акт возвращён в очередь — схема будет построена заново')
    } catch (e) {
      message.error(e.message)
    }
  }

  const save = async (andNext) => {
    const hasPicture = !!(picture || pictureSrc)
    if (!hasPicture) setPictureError(true)
    const v = await form.validateFields()
    if (!hasPicture) {
      message.error('Добавьте ситуационный план — акт без картинки не сохраняется')
      return
    }
    setSaving(true)
    try {
      const act = isNew ? await api.createAct(v) : await api.updateAct(id, v)
      if (picture) await api.setPicture(act.id, picture)
      const changed = form.isFieldsTouched() || !!picture
      if (!isNew && status === 'done' && changed && await askRedo()) {
        await api.reopenAct(act.id)
        setStatus('new')
        message.success('Акт сохранён и возвращён в очередь — схема будет построена заново')
      } else {
        message.success(isNew ? `Акт ${act.number} добавлен` : 'Акт сохранён')
      }
      if (andNext) {
        // следующий акт того же завода/цеха/установки и с теми же конструкциями — обычно акты идут пачкой
        const keep = {
          refinery: v.refinery, department: v.department, facility: v.facility,
          date: v.date, number: v.number,
          constructions: (v.constructions || []).map((c) => ({ ...c })),
        }
        const prev = { number: act.number, date: act.date }
        if (isNew) {
          setPicture(null)
          setPictureSrc(null)
          setPictureError(false)
          form.setFieldsValue({ ...EMPTY, ...keep })
          setPrevAct(prev)
        } else {
          navigate('/acts/new', { state: { keep, prev } })
        }
      } else {
        navigate('/')
      }
    } catch (e) {
      message.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Form form={form} layout="vertical" initialValues={EMPTY} requiredMark={false}>
      <div className="mb-4 flex items-baseline gap-3">
        <h1 className="m-0 text-[28px] font-bold tracking-tight">{isNew ? 'Новый акт' : `Акт № ${values.number || ''}`}</h1>
      </div>
      {status === 'done' && (
        <Alert className="!mb-4" type="success" showIcon
          message="Схема по этому акту уже построена"
          description="Если что-то изменили — сохраните акт и согласитесь переделать схему, или верните акт в очередь кнопкой справа."
          action={<Button icon={<RedoOutlined />} onClick={redo}>Переделать</Button>} />
      )}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_380px]">
        <div className="flex flex-col gap-4">
          <Card title="Реквизиты">
            <div className="grid grid-cols-1 gap-x-4 md:grid-cols-3">
              <Form.Item name="number" label="Номер акта" rules={[{ required: true, message: 'Укажите номер' }]}>
                <Input placeholder="AK-717" />
              </Form.Item>
              <Form.Item name="date" label="Дата акта"
                rules={[{ required: true, message: 'Укажите дату' }, { pattern: DATE_RE, message: 'Формат ДД.ММ.ГГГГ' }]}>
                <Input placeholder="24.06.2026" />
              </Form.Item>
              <Form.Item name="refinery" label="Завод" rules={[{ required: true, message: 'Выберите завод' }]}>
                <Select options={refineryOptions} placeholder="Завод" />
              </Form.Item>
              <Form.Item name="department" label="Цех / объект" rules={[{ required: true, message: 'Укажите цех' }]}
                extra={<AbbrHint value={values.department} />}>
                <Input placeholder="Цех №2" />
              </Form.Item>
              <Form.Item name="facility" label="Установка / производство (необязательно)"
                extra={<AbbrHint value={values.facility} />}>
                <Input placeholder="36-1-2" />
              </Form.Item>
              <Form.Item name="location" label="Дополнительное место">
                <Input />
              </Form.Item>
              <Form.Item name="isp_number" label="Номер ИС" extra="Можно оставить пустым и назначить пачкой в списке актов">
                <InputNumber min={1} className="w-full" />
              </Form.Item>
            </div>
          </Card>
          <Card title="Конструкции">
            <ConstructionsList />
          </Card>
        </div>

        <div className="flex flex-col gap-4">
          <Card title="Ситуационный план" size="small">
            <PicturePaste src={picture || pictureSrc} onPicture={onPicture} error={pictureError} />
          </Card>
          <Card size="small">
            <TitlePreview values={values} settings={settings} />
          </Card>
          <div className="flex flex-col gap-2">
            <Button type="primary" size="large" block loading={saving} onClick={() => save(true)}>
              Сохранить акт и продолжить
            </Button>
            <Button size="large" block color="default" variant="filled" loading={saving} onClick={() => save(false)}>
              Сохранить
            </Button>
            <Button type="text" block onClick={() => navigate('/')}>Отмена</Button>
          </div>
          {prevAct && (
            <div className="flex items-center gap-3 rounded-[14px] bg-white px-4 py-3 shadow-[0_1px_2px_rgba(0,0,0,0.04),0_2px_12px_rgba(0,0,0,0.04)]">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#34c759]/12 text-[#34c759]">
                <HistoryOutlined />
              </div>
              <div className="flex flex-col">
                <span className="text-xs uppercase tracking-wide text-[#8e8e93]">Предыдущий акт</span>
                <span className="font-medium">№ {prevAct.number} от {prevAct.date}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </Form>
  )
}
