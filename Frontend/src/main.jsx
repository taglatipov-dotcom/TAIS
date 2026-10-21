import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App as AntApp, ConfigProvider } from 'antd'
import ruRU from 'antd/locale/ru_RU'
import App from './App.jsx'
import './index.css'

// Оформление в духе iOS: системный шрифт, светло-серый фон, белые скруглённые карточки,
// системные цвета (синий, зелёный, оранжевый, красный).
const FONT = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", ' +
  'Roboto, "Helvetica Neue", Arial, sans-serif'

const theme = {
  token: {
    colorPrimary: '#007aff',
    colorSuccess: '#34c759',
    colorWarning: '#ff9500',
    colorError: '#ff3b30',
    colorInfo: '#007aff',
    blue: '#007aff',
    green: '#34c759',
    colorText: '#1c1c1e',
    colorTextSecondary: '#8e8e93',
    colorBorder: '#d1d1d6',
    colorBorderSecondary: '#e5e5ea',
    colorBgLayout: '#f2f2f7',
    fontFamily: FONT,
    fontSize: 14,
    borderRadius: 10,
    borderRadiusLG: 14,
    borderRadiusSM: 8,
    controlHeight: 36,
    boxShadowSecondary: '0 8px 32px rgba(0, 0, 0, 0.12)',
  },
  components: {
    Button: { primaryShadow: 'none', defaultShadow: 'none', dangerShadow: 'none', fontWeight: 500 },
    Card: { headerFontSize: 17, headerHeight: 52 },
    Table: { headerBg: '#ffffff', headerColor: '#8e8e93', headerSplitColor: 'transparent', rowHoverBg: '#f7f7fa' },
    Segmented: { itemSelectedBg: '#ffffff', trackBg: 'rgba(118, 118, 128, 0.12)', trackPadding: 2 },
    Modal: { titleFontSize: 17 },
    Input: { activeShadow: '0 0 0 3px rgba(0, 122, 255, 0.15)' },
    InputNumber: { activeShadow: '0 0 0 3px rgba(0, 122, 255, 0.15)' },
    Select: { activeOutlineColor: 'rgba(0, 122, 255, 0.15)' },
    Descriptions: { labelBg: '#f7f7fa' },
    Progress: { defaultColor: '#007aff', remainingColor: 'rgba(118, 118, 128, 0.16)' },
  },
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ConfigProvider locale={ruRU} theme={theme}>
      <AntApp>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  </StrictMode>,
)
