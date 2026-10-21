import { useEffect, useRef, useState } from 'react'
import { Layout, Result, Segmented, Tag, Tooltip } from 'antd'
import { BarChartOutlined, BuildOutlined, FileTextOutlined, LoadingOutlined, LockOutlined, PlayCircleOutlined, SettingOutlined } from '@ant-design/icons'
import { Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import Acts from './pages/Acts.jsx'
import ActEdit from './pages/ActEdit.jsx'
import Work from './pages/Work.jsx'
import Generator from './pages/Generator.jsx'
import Settings from './pages/Settings.jsx'
import Analytics from './pages/Analytics.jsx'
import StatusFlags from './components/CadStatus.jsx'
import { DEMO_EVENT, api } from './api.js'
import { BuildProvider, useBuild } from './components/BuildRunner.jsx'

const items = [
  { value: '/', icon: <FileTextOutlined />, label: 'Акты' },
  { value: '/work', icon: <PlayCircleOutlined />, label: 'Отработка' },
  { value: '/analytics', icon: <BarChartOutlined />, label: 'Аналитика' },
  { value: '/generator', icon: <BuildOutlined />, label: 'Генератор' },
  { value: '/settings', icon: <SettingOutlined />, label: 'Настройки' },
]

// Демо-версия: срок и блокировка после окончания (сервер тоже закрывает API)
function useDemo() {
  const [demo, setDemo] = useState(null)
  useEffect(() => {
    const load = () => api.demo().then(setDemo).catch(() => {})
    load()
    const id = setInterval(load, 10 * 60 * 1000)
    window.addEventListener(DEMO_EVENT, load)
    return () => {
      clearInterval(id)
      window.removeEventListener(DEMO_EVENT, load)
    }
  }, [])
  return demo
}

function DemoBadge({ demo }) {
  if (!demo?.demo || demo.expired) return null
  const soon = demo.days_left <= 3
  return (
    <Tooltip title={`Осталось дней: ${demo.days_left}`}>
      <Tag color={soon ? 'orange' : 'blue'} className="!m-0 !rounded-full !px-3 !py-0.5">Демо до {demo.until}</Tag>
    </Tooltip>
  )
}

// Идёт построение (в том числе авто-режим) — видно с любого экрана, клик ведёт на «Отработку»
function BuildBadge() {
  const { busy, auto } = useBuild()
  const navigate = useNavigate()
  if (!busy) return null
  const text = auto ? `Авто: ${auto.index + 1} из ${auto.total}` : busy.kind === 'auto' ? 'Авто-режим' : 'Построение…'
  return (
    <Tag color="processing" icon={<LoadingOutlined />} className="!m-0 cursor-pointer !rounded-full !px-3 !py-0.5"
      onClick={() => busy.kind !== 'generator' && navigate('/work')}>
      {text}
    </Tag>
  )
}

function Shell() {
  const demo = useDemo()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const selected = pathname.startsWith('/acts') ? '/' : (items.find((i) => i.value === pathname)?.value || '/')
  const checked = useRef(false)

  // Шаблон не найден (нет встроенного и не указан свой) — сразу открываем настройки
  useEffect(() => {
    if (checked.current) return
    checked.current = true
    api.cadStatus().then((s) => {
      if (!s.template_ok) navigate('/settings')
    }).catch(() => {})
  }, [navigate])

  return (
    <Layout className="min-h-full !bg-transparent">
      <header className="ios-header">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-6 px-6">
          <div className="flex items-center gap-2">
            <img src="/logo.svg" alt="" className="h-7 w-7" />
            <span className="text-[19px] font-semibold tracking-tight">TAIS</span>
          </div>
          {!demo?.expired && <Segmented className="ios-nav" value={selected} options={items} onChange={(v) => navigate(v)} />}
          <div className="ml-auto flex items-center gap-3">
            {!demo?.expired && <BuildBadge />}
            <DemoBadge demo={demo} />
            {!demo?.expired && <StatusFlags />}
          </div>
        </div>
      </header>
      <Layout.Content className="px-6 py-6">
        <div className="mx-auto max-w-[1400px]">
          {demo?.expired
            ? (
              <Result icon={<LockOutlined className="!text-[#8e8e93]" />}
                title={demo.reason === 'clock' ? 'Неверная дата на компьютере' : 'Демо-версия закончилась'}
                subTitle={demo.message} />
            )
            : <div key={selected} className="page"><Outlet /></div>}
        </div>
      </Layout.Content>
    </Layout>
  )
}

// BuildProvider — над маршрутами: построение и окна готовности переживают смену экрана
export default function App() {
  return (
    <BuildProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<Acts />} />
          <Route path="acts/new" element={<ActEdit />} />
          <Route path="acts/:id" element={<ActEdit />} />
          <Route path="work" element={<Work />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="generator" element={<Generator />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Acts />} />
        </Route>
      </Routes>
    </BuildProvider>
  )
}
