import { useState } from 'react'
import { App, Button, Card, Form } from 'antd'
import { CalculatorOutlined, FolderOpenOutlined, SendOutlined } from '@ant-design/icons'
import { api, desktop } from '../api.js'
import ConstructionsList, { NEW_CONSTRUCTION } from '../components/ConstructionsList.jsx'
import SchemeView from '../components/SchemeView.jsx'
import { PrintButton } from '../components/SchemeActions.jsx'
import { useBuild } from '../components/BuildRunner.jsx'

// Быстрая проверка генератора без акта: одна или несколько конструкций на схеме
export default function Generator() {
  const { message } = App.useApp()
  const { busy, lastFiles, buildScheme } = useBuild()
  const building = busy?.kind === 'generator'
  const lastFile = lastFiles.generator
  const [form] = Form.useForm()
  const [scheme, setScheme] = useState(null)
  const [loading, setLoading] = useState(false)

  const calculate = async () => {
    const values = await form.validateFields()
    setLoading(true)
    try {
      setScheme(await api.scheme(values))
    } catch (e) {
      message.error(e.message)
    } finally {
      setLoading(false)
    }
  }

  // построение — в BuildRunner: окно «Чертёж сформирован» не пропадёт при смене экрана
  const build = async () => {
    const values = await form.validateFields()
    await buildScheme(values)
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="m-0 text-[28px] font-bold tracking-tight">Генератор</h1>
      <Card title="Конструкции на схеме"
        extra={
          <div className="flex flex-wrap gap-2">
            <Button color="default" variant="filled" icon={<CalculatorOutlined />} loading={loading} onClick={calculate}>
              Рассчитать
            </Button>
            <Button type="primary" icon={<SendOutlined />} loading={building} onClick={build}
              disabled={!!busy && !building}>
              Построить в nanoCAD
            </Button>
            <PrintButton file={busy ? null : lastFile} />
            {desktop && (
              <Button type="text" icon={<FolderOpenOutlined />}
                onClick={() => api.getSettings().then((s) => desktop.openPath(s.output_dir))}>
                Папка чертежей
              </Button>
            )}
          </div>
        }>
        <Form form={form} layout="vertical" initialValues={{ constructions: [{ ...NEW_CONSTRUCTION, length: 3, width: 2 }] }}>
          <ConstructionsList />
        </Form>
      </Card>
      {scheme && <Card><SchemeView scheme={scheme} /></Card>}
    </div>
  )
}
