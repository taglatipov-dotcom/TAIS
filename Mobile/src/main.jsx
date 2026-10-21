import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import { App as AntApp, ConfigProvider } from 'antd'
import ruRU from 'antd/locale/ru_RU'
import App from './App.jsx'
import './index.css'

// Оформление — как у настольного TAIS (в духе iOS), под размеры телефона
const FONT = '-apple-system, BlinkMacSystemFont, "SF Pro Text", Roboto, "Helvetica Neue", Arial, sans-serif'

const theme = {
  token: {
    colorPrimary: '#007aff',
    colorSuccess: '#34c759',
    colorWarning: '#ff9500',
    colorError: '#ff3b30',
    colorInfo: '#007aff',
    colorText: '#1c1c1e',
    colorTextSecondary: '#8e8e93',
    colorBorder: '#d1d1d6',
    colorBorderSecondary: '#e5e5ea',
    colorBgLayout: '#f2f2f7',
    fontFamily: FONT,
    fontSize: 15,
    borderRadius: 10,
    borderRadiusLG: 14,
    controlHeight: 40,
    controlHeightLG: 48,
  },
  components: {
    Button: { primaryShadow: 'none', defaultShadow: 'none', dangerShadow: 'none', fontWeight: 600 },
    Segmented: { itemSelectedBg: '#ffffff', trackBg: 'rgba(118, 118, 128, 0.12)', trackPadding: 2 },
    Input: { activeShadow: '0 0 0 3px rgba(0, 122, 255, 0.15)' },
    InputNumber: { activeShadow: '0 0 0 3px rgba(0, 122, 255, 0.15)' },
    Form: { itemMarginBottom: 12, verticalLabelPadding: '0 0 4px' },
  },
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ConfigProvider locale={ruRU} theme={theme}>
      <AntApp>
        <HashRouter>
          <App />
        </HashRouter>
      </AntApp>
    </ConfigProvider>
  </StrictMode>,
)
