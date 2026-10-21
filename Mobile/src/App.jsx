import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { CalculatorOutlined, SettingOutlined } from '@ant-design/icons'
import { Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import Calc from './pages/Calc.jsx'
import Result from './pages/Result.jsx'
import Settings from './pages/Settings.jsx'
import { applyWeights, loadUserWeights, saveUserWeights } from './weights.js'

// Общее состояние: последний расчёт и свои веса элементов
const Store = createContext(null)
export const useStore = () => useContext(Store)

const TABS = [
  { path: '/', icon: <CalculatorOutlined />, label: 'Расчёт' },
  { path: '/settings', icon: <SettingOutlined />, label: 'Настройки' },
]

function TabBar() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const active = pathname.startsWith('/settings') ? '/settings' : '/'
  return (
    <nav className="tabbar">
      {TABS.map((t) => (
        <button key={t.path} type="button" className={`tab ${active === t.path ? 'tab-active' : ''}`}
          onClick={() => navigate(t.path)}>
          <span className="text-[22px] leading-none">{t.icon}</span>
          <span className="text-[11px] font-medium">{t.label}</span>
        </button>
      ))}
    </nav>
  )
}

export default function App() {
  const [weights, setWeightsState] = useState(loadUserWeights)
  const [result, setResult] = useState(null) // { scheme, items }

  // веса подставляются в генератор спецификации до первого расчёта и при каждом изменении
  useMemo(() => applyWeights(weights), [weights])

  const setWeights = (next) => {
    setWeightsState(next)
    saveUserWeights(next)
  }

  useEffect(() => {
    document.title = 'TAIS'
  }, [])

  const store = { weights, setWeights, result, setResult }
  return (
    <Store.Provider value={store}>
      <div className="app">
        <main className="app-main">
          <Routes>
            <Route path="/" element={<Calc />} />
            <Route path="/result" element={<Result />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Calc />} />
          </Routes>
        </main>
        <TabBar />
      </div>
    </Store.Provider>
  )
}
