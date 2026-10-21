import { useMemo, useState } from 'react'
import { Button, Modal } from 'antd'
import { ExpandOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons'

// Три вида по элементам генератора (как Preview.jsx настольного TAIS), без 3D-движка
const COLORS = {
  post: 'var(--c-post)',
  jack: 'var(--c-post)',
  ledger: 'var(--c-ledger)',
  diagonal: 'var(--c-diagonal)',
  toeboard: 'var(--c-toeboard)',
  deck: 'var(--c-deck)',
  hatch: 'var(--c-ladder)',
}

const LEGEND = [
  ['post', 'Стойки'], ['ledger', 'Ригели'], ['diagonal', 'Диагонали'],
  ['deck', 'Настилы'], ['toeboard', 'Бортики'], ['hatch', 'Люки'],
]

const VIEWS = {
  front: { title: 'Вид спереди', u: (p) => p[0], v: (p) => p[2] },
  side: { title: 'Вид сбоку', u: (p) => p[1], v: (p) => p[2] },
  top: { title: 'Вид сверху', u: (p) => p[0], v: (p) => p[1] },
}

function shapes(elements, view) {
  const { u, v } = VIEWS[view]
  const lines = []
  const rects = []
  const polys = []
  for (const e of elements) {
    if (e.poly && view === 'top') {
      polys.push({ pts: e.poly, kind: e.kind })
    } else if (e.seg) {
      const [a, b] = e.seg
      if (view === 'top' && e.kind === 'post') continue
      lines.push({ x1: u(a), y1: v(a), x2: u(b), y2: v(b), kind: e.kind })
    } else if (e.box && view === 'top') {
      const [x, y, w, h] = e.box
      rects.push({ x, y, w, h, kind: e.kind })
    } else if (e.box) {
      const [x, y, w, h] = e.box
      const a = [x, y, e.z]
      const b = [x + w, y + h, e.z]
      lines.push({ x1: u(a), y1: v(a), x2: u(b), y2: v(b), kind: e.kind })
    }
  }
  return { lines, rects, polys }
}

function bounds({ lines, rects, polys }) {
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  const add = (x, y) => {
    minX = Math.min(minX, x); maxX = Math.max(maxX, x)
    minY = Math.min(minY, y); maxY = Math.max(maxY, y)
  }
  for (const l of lines) { add(l.x1, l.y1); add(l.x2, l.y2) }
  for (const r of rects) { add(r.x, r.y); add(r.x + r.w, r.y + r.h) }
  for (const p of polys) for (const [x, y] of p.pts) add(x, y)
  return minX === Infinity ? null : { minX, maxX, minY, maxY }
}

function ViewSvg({ data, className, style }) {
  const b = bounds(data)
  if (!b) return null
  const pad = 300
  const minX = b.minX - pad
  const maxX = b.maxX + pad
  const minY = b.minY - pad
  const maxY = b.maxY + pad
  const fy = (y) => maxY + minY - y // ось Y экрана направлена вниз
  const stroke = Math.max(maxX - minX, maxY - minY) / 300
  const { lines, rects, polys } = data
  return (
    <svg viewBox={`${minX} ${minY} ${maxX - minX} ${maxY - minY}`} className={className} style={style}
      preserveAspectRatio="xMidYMid meet">
      {rects.map((r, i) => (
        <rect key={`r${i}`} x={r.x} y={fy(r.y + r.h)} width={r.w} height={r.h}
          fill={COLORS[r.kind]} fillOpacity={0.25} stroke={COLORS[r.kind]} strokeWidth={stroke / 2} />
      ))}
      {polys.map((p, i) => (
        <polygon key={`p${i}`} points={p.pts.map(([x, y]) => `${x},${fy(y)}`).join(' ')}
          fill={COLORS[p.kind]} fillOpacity={0.25} stroke={COLORS[p.kind]} strokeWidth={stroke / 2} />
      ))}
      {lines.map((l, i) => (
        <line key={`l${i}`} x1={l.x1} y1={fy(l.y1)} x2={l.x2} y2={fy(l.y2)}
          stroke={COLORS[l.kind] || '#6b7280'} strokeWidth={l.kind === 'post' ? stroke * 1.6 : stroke} />
      ))}
    </svg>
  )
}

// Вид во весь экран: кнопки масштаба, прокрутка пальцем
function Fullscreen({ data, title, onClose }) {
  const [zoom, setZoom] = useState(1)
  return (
    <Modal open title={title} onCancel={onClose} footer={null} width="100%" centered
      className="view-modal" styles={{ body: { padding: 0 } }}>
      <div className="view-scroll">
        <ViewSvg data={data} style={{ width: `${zoom * 100}%`, height: `${zoom * 70}vh` }} />
      </div>
      <div className="flex items-center justify-center gap-3 py-3">
        <Button shape="circle" icon={<ZoomOutOutlined />} disabled={zoom <= 1} onClick={() => setZoom(Math.max(1, zoom / 1.5))} />
        <span className="w-14 text-center text-[13px] text-[#8e8e93]">{Math.round(zoom * 100)}%</span>
        <Button shape="circle" icon={<ZoomInOutlined />} disabled={zoom >= 8} onClick={() => setZoom(Math.min(8, zoom * 1.5))} />
      </div>
    </Modal>
  )
}

function View({ elements, view }) {
  const data = useMemo(() => shapes(elements, view), [elements, view])
  const [open, setOpen] = useState(false)
  return (
    <figure className="card m-0 !p-2">
      <div className="flex items-center justify-between px-2 pb-1">
        <figcaption className="text-[15px] font-semibold">{VIEWS[view].title}</figcaption>
        <Button type="text" size="small" icon={<ExpandOutlined />} onClick={() => setOpen(true)}>Увеличить</Button>
      </div>
      <button type="button" className="block w-full" onClick={() => setOpen(true)} aria-label={VIEWS[view].title}>
        <ViewSvg data={data} className="h-64 w-full rounded-lg bg-white" />
      </button>
      {open && <Fullscreen data={data} title={VIEWS[view].title} onClose={() => setOpen(false)} />}
    </figure>
  )
}

export default function Views({ elements }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="legend">
        {LEGEND.map(([k, label]) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <i className="inline-block h-[3px] w-4 rounded" style={{ background: COLORS[k] }} />{label}
          </span>
        ))}
      </div>
      <View elements={elements} view="front" />
      <View elements={elements} view="side" />
      <View elements={elements} view="top" />
    </div>
  )
}
