import { useEffect, useMemo, useRef, useState } from 'react'

// Простые SVG-графики без сторонних библиотек: столбцы по дням и кольцевая диаграмма.
// Цвета категорий — в фиксированном порядке (проверены на различимость при дальтонизме),
// «Другие» — всегда серый.
export const SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#6250d6', '#008300']
export const OTHER = '#b8b8c0'

function useWidth() {
  const ref = useRef(null)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    if (!ref.current) return
    const ro = new ResizeObserver(([e]) => setWidth(Math.floor(e.contentRect.width)))
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [])
  return [ref, width]
}

// «Красивый» шаг сетки: 1, 2, 5 × 10ⁿ
function niceMax(v, integer, ticks = 4) {
  if (v <= 0) return { max: ticks, step: 1 }
  const raw = v / ticks
  const mag = 10 ** Math.floor(Math.log10(raw))
  let step = [1, 2, 5, 10].map((m) => m * mag).find((x) => x >= raw)
  if (integer) step = Math.max(1, step)
  return { max: Math.ceil(v / step) * step, step }
}

// столбик со скруглённой верхушкой (4px), основание прямое
function barPath(x, y, w, h, r = 4) {
  if (h <= 0) return ''
  const rr = Math.min(r, w / 2, h)
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`
}

const fmt = (v) => v.toLocaleString('ru-RU', { maximumFractionDigits: 1 })
const MONTHS = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
const WEEKDAYS = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб']
const parseDay = (s) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d) }
export const dayLabel = (s) => { const d = parseDay(s); return `${d.getDate()} ${MONTHS[d.getMonth()]}` }

export function DailyBars({ data, field = 'count', unit = '', height = 260, color = SERIES[0] }) {
  const [ref, width] = useWidth()
  const [hover, setHover] = useState(null)
  const pad = { top: 16, right: 12, bottom: 28, left: 40 }
  const values = data.map((d) => d[field])
  const top = Math.max(0, ...values)
  const { max, step } = useMemo(() => niceMax(top, field === 'count'), [top, field])
  const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0
  const innerW = Math.max(0, width - pad.left - pad.right)
  const innerH = height - pad.top - pad.bottom
  const slot = data.length ? innerW / data.length : 0
  const gap = Math.max(2, Math.min(6, slot * 0.25))
  const bw = Math.max(1, slot - gap)
  const y = (v) => pad.top + innerH - (v / max) * innerH
  const ticks = []
  for (let v = 0; v <= max + 1e-9; v += step) ticks.push(Math.round(v * 100) / 100)
  const labelEvery = Math.max(1, Math.ceil(data.length / Math.max(1, Math.floor(innerW / 56))))
  const h = hover != null ? data[hover] : null

  return (
    <div ref={ref} className="relative w-full select-none" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label="Выполнено по дням"
          onMouseLeave={() => setHover(null)}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={pad.left} x2={width - pad.right} y1={y(t)} y2={y(t)}
                stroke={t === 0 ? '#c7c7cc' : '#ececf0'} strokeDasharray={t === 0 ? '' : '3 4'} />
              <text x={pad.left - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize="11" fill="#8e8e93">{fmt(t)}</text>
            </g>
          ))}
          {data.map((d, i) => {
            const x = pad.left + i * slot + gap / 2
            const v = d[field]
            const dim = hover != null && hover !== i
            return (
              <g key={d.date}>
                <path d={barPath(x, y(v), bw, y(0) - y(v))} fill={color} opacity={dim ? 0.35 : 1}
                  style={{ transition: 'opacity .15s, d .4s' }} />
                {v === 0 && <rect x={x} y={y(0) - 2} width={bw} height={2} rx={1} fill="#e5e5ea" />}
                {i % labelEvery === (data.length - 1) % labelEvery && (
                  <text x={x + bw / 2} y={height - 8} textAnchor="middle" fontSize="11"
                    fill={i === data.length - 1 ? '#1c1c1e' : '#8e8e93'} fontWeight={i === data.length - 1 ? 600 : 400}>
                    {i === data.length - 1 ? 'сегодня' : dayLabel(d.date)}
                  </text>
                )}
                {/* зона наведения шире столбика */}
                <rect x={pad.left + i * slot} y={pad.top} width={slot} height={innerH} fill="transparent"
                  onMouseEnter={() => setHover(i)} />
              </g>
            )
          })}
          {avg > 0 && (
            <g pointerEvents="none">
              <line x1={pad.left} x2={width - pad.right} y1={y(avg)} y2={y(avg)} stroke="#1c1c1e" strokeOpacity=".45"
                strokeWidth="1.5" strokeDasharray="6 4" />
              <text x={width - pad.right} y={y(avg) - 6} textAnchor="end" fontSize="11" fill="#636366"
                stroke="#fff" strokeWidth="4" paintOrder="stroke" strokeLinejoin="round">
                среднее {fmt(avg)}{unit && ` ${unit}`}
              </text>
            </g>
          )}
        </svg>
      )}
      {h && (
        <div className="chart-tip" style={{
          left: Math.min(Math.max(pad.left + hover * slot + slot / 2, 70), width - 70),
          top: Math.max(0, y(h[field]) - 8),
        }}>
          <div className="text-[11px] text-[#8e8e93]">{WEEKDAYS[parseDay(h.date).getDay()]}, {dayLabel(h.date)}</div>
          <div className="text-[15px] font-semibold">{fmt(h[field])}{unit && ` ${unit}`}</div>
        </div>
      )}
    </div>
  )
}

// Кольцевая диаграмма: в центре — итог (или наведённый сектор), справа — легенда со значениями
export function Donut({ items, size = 168, thickness = 22, total: totalLabel = 'всего' }) {
  const [hover, setHover] = useState(null)
  const total = items.reduce((a, b) => a + b.value, 0)
  const r = (size - thickness) / 2
  const c = size / 2
  const circ = 2 * Math.PI * r
  const gapLen = items.filter((i) => i.value > 0).length > 1 ? 3 : 0
  let acc = 0
  const segs = items.map((it, i) => {
    const len = total ? (it.value / total) * circ : 0
    const seg = { ...it, i, len: Math.max(0, len - gapLen), offset: acc }
    acc += len
    return seg
  })
  const h = hover != null ? items[hover] : null
  const pct = (v) => (total ? Math.round((v / total) * 100) : 0)

  return (
    <div className="flex flex-wrap items-center gap-5">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Круговая диаграмма">
          <circle cx={c} cy={c} r={r} fill="none" stroke="#f2f2f7" strokeWidth={thickness} />
          <g transform={`rotate(-90 ${c} ${c})`}>
            {segs.map((s) => s.len > 0 && (
              <circle key={s.key} cx={c} cy={c} r={r} fill="none" stroke={s.color}
                strokeWidth={hover === s.i ? thickness + 6 : thickness}
                strokeDasharray={`${s.len} ${circ - s.len}`} strokeDashoffset={-s.offset}
                opacity={hover != null && hover !== s.i ? 0.35 : 1}
                style={{ transition: 'stroke-width .15s, opacity .15s', cursor: 'default' }}
                onMouseEnter={() => setHover(s.i)} onMouseLeave={() => setHover(null)} />
            ))}
          </g>
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
          <div className="text-[26px] font-bold leading-none tracking-tight">{fmt(h ? h.value : total)}</div>
          <div className="mt-1 max-w-[96px] truncate text-[12px] text-[#8e8e93]">{h ? `${pct(h.value)}% · ${h.label}` : totalLabel}</div>
        </div>
      </div>
      <ul className="m-0 flex min-w-[140px] flex-1 list-none flex-col gap-1.5 p-0">
        {items.map((it, i) => (
          <li key={it.key} className={`donut-row ${hover === i ? 'is-active' : ''}`}
            onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: it.color }} />
            <span className="min-w-0 flex-1 truncate">{it.label}</span>
            <span className="font-semibold tabular-nums">{fmt(it.value)}</span>
            <span className="w-9 text-right text-[12px] tabular-nums text-[#8e8e93]">{pct(it.value)}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

// Горизонтальные полосы — рейтинг (цеха и т.п.)
export function BarList({ items, color = SERIES[0] }) {
  const max = Math.max(1, ...items.map((i) => i.value))
  return (
    <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
      {items.map((it) => (
        <li key={it.key} title={`${it.label}: ${it.value}`}>
          <div className="mb-1 flex justify-between gap-3 text-[13px]">
            <span className="truncate">{it.label}</span>
            <span className="font-semibold tabular-nums">{fmt(it.value)}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-[#f2f2f7]">
            <div className="h-full rounded-full" style={{ width: `${(it.value / max) * 100}%`, background: it.key === '__other__' ? OTHER : color, transition: 'width .5s' }} />
          </div>
        </li>
      ))}
    </ul>
  )
}
