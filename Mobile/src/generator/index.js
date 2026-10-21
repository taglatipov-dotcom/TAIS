// Генератор строительных лесов для мобильного приложения — перенос Backend/tais/generator
// (run, scheme.run_scheme) и проверки из app._scheme. При изменении правил в Python
// переносить сюда же и обновлять эталоны: python tools/make_golden.py → npm test.
import { SplitError } from './bays.js'
import { ATTACHABLE, KINDS, SIDES, buildGroup, classify, makeInput } from './constructions.js'
import { wideningLevels } from './model.js'
import { runRadial } from './radial.js'
import { generate } from './rules.js'
import * as spec from './spec.js'
import { fmtG, pairs, pyRound, sortNum } from './py.js'

export { KINDS, SIDES, ATTACHABLE, SplitError, classify, spec }

const GAP = 1000 // зазор между конструкциями на схеме, мм

export const specification = (elements) => spec.build(elements.map((e) => e.article))

// Полный расчёт одной конструкции (с пристроенными уширениями)
export function run(inp, widenings = []) {
  if (inp.kind === 'radial') return runRadial(inp, specification)
  const [st, notes] = buildGroup(inp, widenings)
  const gen = generate(st)
  const cells = st.allCells()
  const widCells = cells.filter((c) => c.role === 'widening')
  const lengthM = st.length / 1000
  const heightM = inp.height
  return {
    input: {
      kind: inp.kind, length: inp.length, width: inp.width, height: inp.height,
      intermediate_decks: inp.intermediate_decks, entrance: inp.entrance, pads: inp.pads,
    },
    grid: {
      xs: st.xs,
      ys: st.ys,
      bays_x: pairs(st.xs).map(([a, b]) => b - a),
      bays_y: pairs(st.ys).map(([a, b]) => b - a),
      top: st.top + st.lift,
      decks: sortNum(new Set(cells.flatMap((c) => [...c.decks]))).map((z) => z + st.lift),
      lift: st.lift,
      widening_levels: sortNum(new Set(widCells.flatMap((c) => wideningLevels(c).map((z) => z + st.lift)))),
    },
    area: { formula: `${fmtG(lengthM)} х ${fmtG(heightM)}`, value: pyRound(lengthM * heightM, 3) },
    elements: gen.elements.map((e) => e.toDict()),
    spec: specification(gen.elements),
    warnings: [...notes, ...gen.warnings],
  }
}

function shift(e, dx, dy = 0.0) {
  const out = { ...e, x: e.x + dx, y: e.y + dy }
  if (e.seg) out.seg = e.seg.map((p) => [p[0] + dx, p[1] + dy, p[2]])
  if (e.box) out.box = [e.box[0] + dx, e.box[1] + dy, e.box[2], e.box[3]]
  return out
}

function toInput(it) {
  let kind = it.kind || 'auto'
  if (kind === 'auto') kind = classify(it.length, it.width)
  return makeInput({
    kind, length: it.length, width: it.width, height: it.height,
    intermediate_decks: it.intermediate_decks ?? true, entrance: it.entrance ?? true, pads: it.pads ?? false,
    attach_to: it.attach_to || null, side: it.side || 'y0', offset: Number(it.offset || 0),
    widening: Boolean(it.widening ?? false), widening_width: Number(it.widening_width || 1.0),
    widening_height: it.widening_height || null,
  })
}

// Конструкции схемы — друг за другом по Y с зазором (tais.cad.views.arrange)
function arrange(parts, gap) {
  const offs = []
  let y = 0.0
  for (const p of parts) {
    const g = p.grid
    offs.push([-g.xs[0], y - g.ys[0]])
    y += (g.ys[g.ys.length - 1] - g.ys[0]) + gap
  }
  return offs
}

export function runScheme(items) {
  if (!items.length) throw new Error('Добавьте хотя бы одну конструкцию')
  const inputs = items.map(toInput)
  const attached = new Map()
  inputs.forEach((inp, idx) => {
    const n = idx + 1
    if (!ATTACHABLE.includes(inp.kind) || !inp.attach_to) {
      inp.attach_to = null
      return
    }
    const t = inp.attach_to
    if (t === n || !(t >= 1 && t <= inputs.length)) {
      throw new SplitError(`Конструкция ${n}: ${KINDS[inp.kind].toLowerCase()} пристроено к ` +
        `несуществующей конструкции №${t}`)
    }
    const target = inputs[t - 1].kind
    if (ATTACHABLE.includes(target) || target === 'radial') {
      throw new SplitError(`Конструкция ${n}: пристраивать можно только к башенным или ` +
        `фасадным лесам (№${t} — ${KINDS[target].toLowerCase()})`)
    }
    if (!attached.has(t)) attached.set(t, [])
    attached.get(t).push(n)
  })

  const results = []
  const parts = []
  const warnings = []
  items.forEach((it, idx) => {
    const n = idx + 1
    const inp = inputs[idx]
    if (inp.attach_to) return
    const wids = attached.get(n) || []
    const res = run(inp, wids.map((k) => inputs[k - 1]))
    results.push(res)
    const prefix = items.length > 1 ? `Конструкция ${n}: ` : ''
    warnings.push(...res.warnings.map((w) => prefix + w))
    parts.push({
      n, kind: inp.kind, kind_label: KINDS[inp.kind],
      length: it.length, width: it.width, height: it.height,
      grid: res.grid,
      widenings: wids.map((k) => {
        const w = inputs[k - 1]
        return {
          n: k, kind: w.kind, kind_label: KINDS[w.kind], length: w.length, width: w.width,
          height: w.height, side: w.side, side_label: SIDES[w.side], offset: w.offset,
        }
      }),
    })
  })

  const elements = []
  arrange(parts, GAP).forEach(([dx, dy], k) => {
    parts[k].offset = dx
    parts[k].offset_y = dy
    for (const e of results[k].elements) elements.push(shift(e, dx, dy))
  })
  return { parts, elements, spec: spec.build(elements.map((e) => e.article)), warnings }
}

// Как POST /api/scheme: проверка типов и высот, ошибки размеров — понятным текстом
export function calculate(items) {
  const list = items.map((it) => ({ ...it }))
  list.forEach((it, idx) => {
    if (!['auto', ...Object.keys(KINDS)].includes(it.kind || 'auto')) throw new Error(`Неизвестный тип: ${it.kind}`)
    if (it.height === null || it.height === undefined || it.height === '') {
      if (it.kind === 'balcony' && it.attach_to) it.height = 0.0
      else throw new Error(`Конструкция ${idx + 1}: укажите высоту`)
    }
  })
  return runScheme(list)
}
