import { useMemo } from 'react'

// Простой предпросмотр трёх видов по элементам генератора (без 3D-движка).
const COLORS = {
  post: 'var(--c-post)',
  jack: 'var(--c-post)',
  ledger: 'var(--c-ledger)',
  diagonal: 'var(--c-diagonal)',
  toeboard: 'var(--c-toeboard)',
  deck: 'var(--c-deck)',
  hatch: 'var(--c-ladder)',
}

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
      // повёрнутый настил (радиальные леса)
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

function View({ elements, view }) {
  const { lines, rects, polys } = useMemo(() => shapes(elements, view), [elements, view])
  const xs = [...lines.flatMap((l) => [l.x1, l.x2]), ...rects.flatMap((r) => [r.x, r.x + r.w]),
    ...polys.flatMap((p) => p.pts.map((q) => q[0]))]
  const ys = [...lines.flatMap((l) => [l.y1, l.y2]), ...rects.flatMap((r) => [r.y, r.y + r.h]),
    ...polys.flatMap((p) => p.pts.map((q) => q[1]))]
  if (!xs.length) return null
  const pad = 300
  const minX = Math.min(...xs) - pad
  const maxX = Math.max(...xs) + pad
  const minY = Math.min(...ys) - pad
  const maxY = Math.max(...ys) + pad
  // ось Y экрана направлена вниз — переворачиваем
  const fy = (y) => maxY + minY - y
  const stroke = Math.max(maxX - minX, maxY - minY) / 300

  return (
    <figure className="m-0 flex flex-col items-center">
      <svg
        viewBox={`${minX} ${minY} ${maxX - minX} ${maxY - minY}`}
        className="w-full h-72 bg-white border border-gray-200 rounded"
        preserveAspectRatio="xMidYMid meet"
      >
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
      <figcaption className="text-sm text-gray-500 mt-1">{VIEWS[view].title}</figcaption>
    </figure>
  )
}

export default function Preview({ elements }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <View elements={elements} view="front" />
      <View elements={elements} view="side" />
      <View elements={elements} view="top" />
    </div>
  )
}
