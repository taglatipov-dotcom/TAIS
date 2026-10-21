import { useCallback, useEffect, useMemo, useState } from 'react'
import { App, Button, Empty, Segmented, Skeleton, Tooltip } from 'antd'
import {
  AppstoreOutlined, CalendarOutlined, CheckCircleOutlined, ClockCircleOutlined, FireOutlined, NumberOutlined,
  ReloadOutlined, RiseOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { api, kindLabel } from '../api.js'
import { useBuild } from '../components/BuildRunner.jsx'
import { BarList, DailyBars, Donut, OTHER, SERIES, dayLabel } from '../components/Charts.jsx'

const PERIODS = [{ value: 14, label: '14 дней' }, { value: 30, label: '30 дней' }, { value: 90, label: '90 дней' }]
const fmt = (v) => (v ?? 0).toLocaleString('ru-RU', { maximumFractionDigits: 1 })

// раскраска разбивок: цвета по порядку, «Другие» — серый
const paint = (rows, label) => rows.map((r, i) => ({
  ...r,
  label: r.key === '__other__' ? 'Другие' : label(r.key),
  color: r.key === '__other__' ? OTHER : SERIES[i % SERIES.length],
}))

function Kpi({ icon, tint, label, value, hint, onClick }) {
  return (
    <div className={`kpi ${onClick ? 'cursor-pointer' : ''}`} onClick={onClick}>
      <div className="kpi-icon" style={{ color: tint, background: `${tint}1a` }}>{icon}</div>
      <div className="min-w-0">
        <div className="text-[13px] text-[#8e8e93]">{label}</div>
        <div className="truncate text-[26px] font-bold leading-tight tracking-tight">{value}</div>
        {hint && <div className="truncate text-[12px] text-[#8e8e93]">{hint}</div>}
      </div>
    </div>
  )
}

function Panel({ title, extra, children, className = '' }) {
  return (
    <section className={`panel ${className}`}>
      <header className="mb-4 flex flex-wrap items-center gap-3">
        <h2 className="m-0 mr-auto text-[17px] font-semibold">{title}</h2>
        {extra}
      </header>
      {children}
    </section>
  )
}

export default function Analytics() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const { version } = useBuild()
  const [days, setDays] = useState(30)
  const [metric, setMetric] = useState('count')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await api.stats(days))
    } catch (e) {
      message.error(e.message)
    } finally {
      setLoading(false)
    }
  }, [days, message])

  // перечитываем после каждого построенного акта
  useEffect(() => { load() }, [load, version])

  const status = useMemo(() => data && [
    { key: 'done', label: 'Готово', value: data.status[0].value, color: '#34c759' },
    { key: 'new', label: 'В работе', value: data.status[1].value, color: '#ff9500' },
  ], [data])
  const kinds = useMemo(() => data && paint(data.kinds, kindLabel), [data])
  const refineries = useMemo(() => data && paint(data.refineries, (k) => (k === '—' ? 'Не указан' : k)), [data])
  const departments = useMemo(() => data && data.departments
    .map((r) => ({ ...r, label: r.key === '__other__' ? 'Другие' : r.key === '—' ? 'Не указан' : r.key })), [data])

  const t = data?.totals
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="mr-auto">
          <h1 className="m-0 text-[28px] font-bold tracking-tight">Аналитика</h1>
          <div className="text-[13px] text-[#8e8e93]">Выполнение актов и исполнительных схем</div>
        </div>
        <Segmented value={days} onChange={setDays} options={PERIODS} />
        <Tooltip title="Обновить">
          <Button color="default" variant="filled" icon={<ReloadOutlined />} onClick={load} loading={loading && !!data} />
        </Tooltip>
      </div>

      {!data ? <Skeleton active paragraph={{ rows: 10 }} /> : (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 2xl:grid-cols-6">
            <Kpi icon={<FireOutlined />} tint="#ff9500" label="Сегодня" value={fmt(t.today)} hint="схем построено" />
            <Kpi icon={<CalendarOutlined />} tint="#007aff" label="На этой неделе" value={fmt(t.week)} hint="с понедельника" />
            <Kpi icon={<RiseOutlined />} tint="#5856d6" label={`За ${days} дней`} value={fmt(t.period)}
              hint={`в среднем ${fmt(t.per_day)} в день`} />
            <Kpi icon={<CheckCircleOutlined />} tint="#34c759" label="Площадь готовых" value={`${Math.round(t.area_done).toLocaleString('ru-RU')} м²`}
              hint={`схем всего: ${fmt(t.done)}`} />
            <Kpi icon={<ClockCircleOutlined />} tint="#ff3b30" label="В работе" value={fmt(t.new)}
              hint={t.without_isp ? `без номера ИС: ${t.without_isp}` : 'все с номерами ИС'}
              onClick={() => navigate('/?status=new')} />
            <Kpi icon={<NumberOutlined />} tint="#30b0c7" label="Последний № ИС" value={data.max_isp ?? '—'}
              hint={data.max_isp_full || 'номера не назначены'}
              onClick={data.max_isp_act ? () => navigate(`/acts/${data.max_isp_act}`) : undefined} />
          </div>

          <Panel title={metric === 'count' ? 'Схем за день' : 'Площадь за день, м²'}
            extra={(
              <>
                {t.best_day && (
                  <span className="text-[13px] text-[#8e8e93]">
                    Рекорд: <b className="text-[#1c1c1e]">{t.best_day.count}</b> — {dayLabel(t.best_day.date)}
                  </span>
                )}
                <Segmented size="small" value={metric} onChange={setMetric}
                  options={[{ value: 'count', label: 'Схемы' }, { value: 'area', label: 'Площадь' }]} />
              </>
            )}>
            {t.period === 0
              ? <Empty className="!my-10" description={`За ${days} дней схем не построено`} />
              : <DailyBars data={data.daily} field={metric} unit={metric === 'area' ? 'м²' : ''}
                  color={metric === 'count' ? SERIES[0] : SERIES[2]} />}
          </Panel>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-4">
            <Panel title="Статус актов">
              {t.acts ? <Donut items={status} total="актов" /> : <Empty description="Актов нет" />}
            </Panel>
            <Panel title="Типы конструкций">
              {t.constructions ? <Donut items={kinds} total="конструкций" /> : <Empty description="Нет конструкций" />}
            </Panel>
            <Panel title="Заводы">
              {t.acts ? <Donut items={refineries} total="актов" /> : <Empty description="Актов нет" />}
            </Panel>
            <Panel title="Цеха" extra={<AppstoreOutlined className="text-[#8e8e93]" />}>
              {t.acts ? <BarList items={departments} /> : <Empty description="Актов нет" />}
            </Panel>
          </div>
        </>
      )}
    </div>
  )
}
