// Рецепты конструкций: из размеров акта строим модель Structure
// (Backend/tais/generator/constructions.py).
import { BAY_SIZES, cumulative, splitLength } from './bays.js'
import { BASE_LEVEL, DECK_STEP, MIN_HEIGHT, NODE_STEP, TOP_FLOOR, Cell, Structure } from './model.js'
import { SplitError, fmtG, pairs, pyRound, range, sortNum } from './py.js'

export const KINDS = {
  tower: 'Башенные',
  facade: 'Фасадные',
  widening: 'Уширение',
  balcony: 'Консольно-опорные леса (балкон)',
  radial: 'Радиальные леса',
}
export const ATTACHABLE = ['widening', 'balcony']

export const BALCONY_POST = 2000
export const BALCONY_BELOW_DECK = 500
export const BALCONY_BRACE = 2000
export const BALCONY_ZONE = TOP_FLOOR + BALCONY_BRACE

export const SIDES = {
  y0: 'передняя сторона',
  y1: 'задняя сторона',
  x0: 'левый торец',
  x1: 'правый торец',
}
export const OPPOSITE = { y0: 'y1', y1: 'y0', x0: 'x1', x1: 'x0' }

// ConstructionInput: длина/ширина/высота — в метрах
export function makeInput({
  kind, length, width, height, intermediate_decks = true, entrance = true, pads = false,
  attach_to = null, side = 'y0', offset = 0, widening = false, widening_width = 1, widening_height = null,
}) {
  return { kind, length, width, height, intermediate_decks, entrance, pads, attach_to, side, offset, widening, widening_width, widening_height }
}

export const toMm = (m) => pyRound(m * 1000)

export function heightPlan(heightMm) {
  const rest = heightMm % NODE_STEP
  let build
  let shift
  if (rest === 0) [build, shift] = [heightMm, 0]
  else if (rest <= 300) [build, shift] = [heightMm - rest, rest]
  else [build, shift] = [heightMm + (NODE_STEP - rest), -(NODE_STEP - rest)]
  if (build < NODE_STEP) {
    shift -= NODE_STEP - build
    build = NODE_STEP
  }
  return [build, shift]
}

export const postsLength = (heightMm) => heightPlan(heightMm)[0]

export function deckLevels(top, intermediate) {
  const topDeck = top - TOP_FLOOR
  if (topDeck <= BASE_LEVEL) return [BASE_LEVEL]
  if (!intermediate) return [topDeck]
  const levels = []
  for (let z = topDeck; z > BASE_LEVEL; z -= DECK_STEP) levels.push(z)
  return sortNum(levels)
}

export function bottomFloor(decks) {
  if (!decks.length) return null
  const low = Math.min(...decks)
  const height = low - BASE_LEVEL
  if (height <= 0 || height >= DECK_STEP) return null
  return { deck: low, height }
}

// Башенные — если L/B < 1.5 или по одному пролёту в каждую сторону
export function classify(lengthM, widthM) {
  if (widthM <= 0) return 'tower'
  const oneBay = Math.max(lengthM, widthM) <= 3.0
  const ratio = Math.max(lengthM, widthM) / Math.min(lengthM, widthM)
  return ratio < 1.5 || oneBay ? 'tower' : 'facade'
}

export function buildStructure(inp, xBreaks = null, yBreaks = null, xBays = null) {
  const length = toMm(inp.length)
  const width = toMm(inp.width)
  const height = toMm(inp.height)
  if (height < MIN_HEIGHT) {
    throw new SplitError(`Конструкции ниже ${fmtG(MIN_HEIGHT / 1000)} м пока не поддерживаются — разбираются отдельно`)
  }
  const xs = xBays ? cumulative(xBays) : cumulative(splitLength(length, xBreaks))
  const ys = cumulative(splitLength(width, yBreaks))
  const top = BASE_LEVEL + postsLength(height)
  if (inp.kind === 'widening') {
    const st = new Structure({ xs, ys, kind: 'widening', lift: heightPlan(height)[1], pads: inp.pads })
    for (const i of range(xs.length - 1)) {
      for (const j of range(ys.length - 1)) {
        st.cells.set(i, j, new Cell({ i, j, decks: new Set(), top, ground: true, role: 'widening', open_side: 'y0' }))
      }
    }
    return st
  }
  if (inp.kind === 'balcony') {
    singleBay(inp)
    const [bottom, deck] = balconyLevels(top)
    const st = new Structure({ xs, ys, kind: 'balcony', lift: heightPlan(height)[1], pads: inp.pads })
    for (const i of range(xs.length - 1)) {
      for (const j of range(ys.length - 1)) {
        st.cells.set(i, j, new Cell({ i, j, decks: new Set([deck]), top, bottom, ground: false, role: 'balcony', open_side: 'y0' }))
      }
    }
    return st
  }
  const levels = deckLevels(top, inp.intermediate_decks)
  const floor = bottomFloor(levels)
  const hatch = levels.filter((z) => z - DECK_STEP >= BASE_LEVEL)
  const groundLadder = floor !== null && (floor.height === 1000 || floor.height === 1500)
  const st = new Structure({
    xs, ys, kind: inp.kind, lift: heightPlan(height)[1],
    entrance_bay: inp.entrance ? 0 : null,
    entrance_line: groundLadder ? ys.length - 1 : 0,
    pads: inp.pads,
  })
  for (const i of range(xs.length - 1)) {
    for (const j of range(ys.length - 1)) {
      const access = i === 0 && j === 0
      st.cells.set(i, j, new Cell({
        i, j, decks: new Set(levels), top, ground: true, access, role: inp.kind,
        hatch_decks: access ? new Set(hatch) : null,
        bottom_floor: access ? floor : null,
      }))
    }
  }
  return st
}

export function balconyLevels(top) {
  const deck = top - TOP_FLOOR
  const bottom = deck - BALCONY_BELOW_DECK
  if (bottom <= BASE_LEVEL) throw new SplitError('Балкон: основная конструкция слишком низкая — нужна высота от 2.5 м')
  return [bottom, deck]
}

function singleBay(inp) {
  if (splitLength(toMm(inp.width)).length !== 1) {
    throw new SplitError(`Балкон: вынос ${fmtG(inp.width)} м должен быть одним пролётом ` +
      '(0.75 / 1.0 / 1.5 / 2.0 / 2.5 / 3.0 м)')
  }
}

function snapHeight(heightMm, lift) {
  const build = pyRound((heightMm - lift) / NODE_STEP) * NODE_STEP
  return Math.max(build, NODE_STEP)
}

const bayText = (lines) => pairs(lines).map(([a, b]) => fmtG((b - a) / 1000)).join(' + ')

// Основная конструкция с пристройками (уширения, балконы) — одна сетка стоек
export function buildGroup(main, widenings, xBays = null) {
  const warnings = []
  if (!widenings.length) return [buildStructure(main, null, null, xBays), warnings]
  const L = toMm(main.length)
  const W = toMm(main.width)
  const xNeed = []
  const yNeed = []
  const taken = {}
  const underBalcony = new Set()
  for (const w of widenings) {
    if (!(w.side in SIDES)) throw new SplitError(`${KINDS[w.kind]}: неизвестная сторона ${w.side}`)
    if (w.kind === 'balcony') singleBay(w)
    const face = w.side === 'y0' || w.side === 'y1' ? L : W
    const a = toMm(w.offset)
    const b = a + toMm(w.length)
    if (a < 0 || b > face) {
      throw new SplitError(
        `${KINDS[w.kind]} ${fmtG(w.length)} м с отступом ${fmtG(w.offset)} м не помещается: ` +
        `${SIDES[w.side]} основной конструкции — ${fmtG(face / 1000)} м`)
    }
    for (const [c, d, other] of taken[w.side] || []) {
      if (a < d && c < b) {
        const kinds = new Set([other.kind, w.kind])
        if (!(kinds.size === 2 && kinds.has('widening') && kinds.has('balcony'))) {
          throw new SplitError(`Пристройки на стороне «${SIDES[w.side]}» перекрываются`)
        }
        underBalcony.add(w.kind === 'widening' ? w : other)
      }
    }
    ;(taken[w.side] ||= []).push([a, b, w])
    ;(w.side === 'y0' || w.side === 'y1' ? xNeed : yNeed).push(a, b)
    if (w.kind === 'widening' && toMm(w.height) < MIN_HEIGHT) {
      throw new SplitError(`Уширения ниже ${fmtG(MIN_HEIGHT / 1000)} м пока не поддерживаются`)
    }
  }

  const plainX = xBays ? cumulative(xBays) : cumulative(splitLength(L))
  const plainY = cumulative(splitLength(W))
  const xBreaks = xNeed.every((p) => plainX.includes(p)) ? null : xNeed
  const yBreaks = yNeed.every((p) => plainY.includes(p)) ? null : yNeed
  const base = buildStructure(main, xBreaks, yBreaks, xBreaks ? null : xBays)

  if (xBreaks) {
    warnings.push('Основная конструкция перестроена под пристройку: пролёты по длине ' +
      `${bayText(plainX)} → ${bayText(base.xs)} м`)
  }
  if (yBreaks) {
    warnings.push('Основная конструкция перестроена под пристройку: пролёты по ширине ' +
      `${bayText(plainY)} → ${bayText(base.ys)} м`)
  }

  const newX = new Set(base.xs)
  const newY = new Set(base.ys)
  const outward = []
  for (const w of widenings) {
    const out = cumulative(splitLength(toMm(w.width)))
    let lines
    if (w.side === 'y0') lines = out.map((v) => -v)
    else if (w.side === 'y1') lines = out.map((v) => W + v)
    else if (w.side === 'x0') lines = out.map((v) => -v)
    else lines = out.map((v) => L + v)
    outward.push(sortNum(lines))
    for (const v of lines) (w.side === 'y0' || w.side === 'y1' ? newY : newX).add(v)
  }
  const sx = Math.min(...newX)
  const sy = Math.min(...newY)
  const xs = sortNum([...newX].map((v) => v - sx))
  const ys = sortNum([...newY].map((v) => v - sy))
  const ix = new Map(xs.map((v, k) => [v + sx, k]))
  const iy = new Map(ys.map((v, k) => [v + sy, k]))

  const st = new Structure({
    xs, ys, kind: base.kind, lift: base.lift,
    entrance_bay: base.entrance_bay === null ? null : ix.get(base.xs[base.entrance_bay]),
    entrance_line: iy.get(base.ys[base.entrance_line]),
    pads: base.pads,
  })
  for (const c of base.cells.values()) {
    c.i = ix.get(base.xs[c.i])
    c.j = iy.get(base.ys[c.j])
    st.cells.set(c.i, c.j, c)
  }
  const mainTop = base.top

  widenings.forEach((w, n) => {
    const lines = outward[n]
    let label
    let make
    if (w.kind === 'balcony') {
      const [bottom, deck] = balconyLevels(mainTop)
      label = `Балкон ${fmtG(w.length)}×${fmtG(w.width)}`
      make = (i, j) => new Cell({
        i, j, decks: new Set([deck]), top: mainTop, bottom, ground: false,
        role: 'balcony', open_side: OPPOSITE[w.side],
      })
    } else {
      const build = snapHeight(toMm(w.height), base.lift)
      const top = BASE_LEVEL + build
      const real = (build + base.lift) / 1000
      label = `Уширение ${fmtG(w.length)}×${fmtG(w.width)}×${fmtG(w.height)}`
      if (Math.abs(real - w.height) > 1e-6) {
        warnings.push(`${label}: высота ${fmtG(real)} м — ригели уширения должны попасть ` +
          'в узлы основной конструкции')
      }
      if (top > mainTop) {
        warnings.push(`${label} выше основной конструкции: стойки основной конструкции ` +
          `на общей стороне наращены до ${fmtG((top + base.lift) / 1000)} м`)
      }
      if (underBalcony.has(w) && top > mainTop - BALCONY_ZONE) {
        const limit = (mainTop - BALCONY_ZONE - BASE_LEVEL + base.lift) / 1000
        throw new SplitError(
          `${label} под балконом: высота не больше ${fmtG(limit)} м — балкон с диагоналями ` +
          `занимает ${fmtG(BALCONY_ZONE / 1000)} м от верха основной конструкции`)
      }
      make = (i, j) => new Cell({
        i, j, decks: new Set(), top, ground: true, role: 'widening', open_side: OPPOSITE[w.side],
      })
    }
    const a = toMm(w.offset)
    const b = a + toMm(w.length)
    let spans
    if (w.side === 'y0' || w.side === 'y1') {
      const along = base.xs.filter((v) => a <= v && v <= b).map((v) => ix.get(v))
      spans = pairs(along).flatMap(([i0, i1]) => pairs(lines).map(([o0, o1]) => [[i0, i1], [iy.get(o0), iy.get(o1)]]))
    } else {
      const along = base.ys.filter((v) => a <= v && v <= b).map((v) => iy.get(v))
      spans = pairs(along).flatMap(([j0, j1]) => pairs(lines).map(([o0, o1]) => [[ix.get(o0), ix.get(o1)], [j0, j1]]))
    }
    for (const [[i0, i1], [j0, j1]] of spans) {
      const fresh = make(i0, j0)
      fresh.i_end = i1
      fresh.j_end = j1
      for (const i of range(i0, i1)) {
        for (const j of range(j0, j1)) {
          const old = st.cells.get(i, j)
          const roles = new Set([old?.role, fresh.role])
          if (old === undefined) {
            st.cells.set(i, j, fresh)
          } else if (roles.size === 2 && roles.has('widening') && roles.has('balcony') && !st.upper.has(i, j)) {
            const [lower, upper] = fresh.role === 'balcony' ? [old, fresh] : [fresh, old]
            st.cells.set(i, j, lower)
            st.upper.set(i, j, upper)
          } else {
            throw new SplitError(`${label} пересекается с другой конструкцией`)
          }
        }
      }
    }
  })
  moveEntrance(st, base, widenings.filter((w) => w.kind === 'widening'), W, warnings)
  return [st, warnings]
}

function moveEntrance(st, base, widenings, W, warnings) {
  if (base.entrance_bay === null) return
  const x = base.xs[base.entrance_bay]
  const blocked = (yLine) => {
    const side = yLine === 0 ? 'y0' : 'y1'
    return widenings.some((w) => w.side === side && toMm(w.offset) <= x && x < toMm(w.offset) + toMm(w.length))
  }
  const yNow = base.ys[base.entrance_line]
  if (!blocked(yNow)) return
  const yOther = yNow === 0 ? W : 0
  if (blocked(yOther)) {
    warnings.push('Входная группа закрыта уширениями с обеих сторон — проверьте вход')
    return
  }
  st.entrance_line = st.ys.indexOf(yOther + (st.ys[st.entrance_line] - yNow))
  warnings.push('Входная группа закрыта уширением — перенесена на противоположную сторону')
}

export { BAY_SIZES }
