import { useState } from 'react'
import { App, Button, Form } from 'antd'
import { CalculatorOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import ConstructionForm, { NEW_CONSTRUCTION } from '../components/ConstructionForm.jsx'
import { calculate } from '../generator/index.js'
import { useStore } from '../App.jsx'

const FORM_KEY = 'tais.form'

// последний ввод сохраняется — после перезапуска приложения не набирать заново
function loadForm() {
  try {
    const v = JSON.parse(localStorage.getItem(FORM_KEY) || 'null')
    if (v?.constructions?.length) return v
  } catch {
    // нет сохранённого ввода
  }
  return { constructions: [{ ...NEW_CONSTRUCTION, length: 3, width: 2 }] }
}

function saveForm(values) {
  try {
    localStorage.setItem(FORM_KEY, JSON.stringify(values))
  } catch {
    // хранилище недоступно
  }
}

export default function Calc() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const { setResult } = useStore()
  const [form] = Form.useForm()
  const [initial] = useState(loadForm)
  const [busy, setBusy] = useState(false)

  const run = async () => {
    let values
    try {
      values = await form.validateFields()
    } catch {
      message.warning('Заполните размеры конструкций')
      return
    }
    setBusy(true)
    // расчёт синхронный: даём кнопке показать загрузку
    setTimeout(() => {
      try {
        const items = values.constructions.map((c) => ({ ...NEW_CONSTRUCTION, ...c }))
        const scheme = calculate(items)
        setResult({ scheme, items })
        navigate('/result')
      } catch (e) {
        message.error({ content: e.message, duration: 6 })
      } finally {
        setBusy(false)
      }
    }, 30)
  }

  return (
    <div className="page">
      <header className="page-header">
        <img src="logo.svg" alt="" className="h-8 w-8" />
        <div>
          <h1 className="page-title">Леса «Союз»</h1>
          <p className="page-subtitle">Размеры конструкций → спецификация и виды</p>
        </div>
      </header>
      <Form form={form} layout="vertical" requiredMark={false} initialValues={initial}
        onValuesChange={(_, all) => saveForm(all)}>
        <ConstructionForm />
      </Form>
      <div className="action-bar">
        <Button type="primary" size="large" block icon={<CalculatorOutlined />} loading={busy} onClick={run}>
          Рассчитать
        </Button>
      </div>
    </div>
  )
}
