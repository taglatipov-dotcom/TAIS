// Правила раскладки элементов по модели Structure (Backend/tais/generator/rules.py).
// Соглашения о точках вставки и сами правила описаны в шапке rules.py.
import * as catalog from './catalog.js'
import { BASE_LEVEL, DECK_STEP, NODE_STEP, Element, ledgerBottom, wideningLevels } from './model.js'
import { floorDiv, fmtG, pad, pairs, pyRound, sortNum } from './py.js'

const POST_PIECE = 3000
const BOTTOM_POST_SIZES = [1000, 1500, 2000, 2500, 3000]
const PLANK_WIDTH = 250
const HATCH_WIDTH = 750
const LADDER_OFFSET = [242, 62, 36]
const GROUND_LADDER_PLANKS = 2
const GROUND_LADDER_DX = 216
const DIAGONAL_EVERY = 1
const DECK_TOLERANCE = 500

export const ART_POST = (n) => `S01062.${pad(n, 4)}`
export const ART_POST_BOTTOM = (n) => `S01022.${pad(n, 4)}`
export const ART_STARTER = 'S01032.0210'
export const ART_JACK = 'U22011.0500'
export const ART_PAD = 'U22061.0300'
export const ART_LEDGER = (n) => `S11013.${pad(n, 4)}`
export const ART_PLANK = (n) => `U00281.${pad(n, 4)}`
export const ART_HATCH = (n) => `U00221.${pad(n, 4)}`
export const ART_TOEBOARD = (n) => `U10012.${pad(n, 4)}`
export const ART_DIAGONAL = (l, h) => `S02012.${pad(l, 3)}${h}`
export const ART_LADDER = 'U07021.2092'

export class Generated {
  constructor() {
    this.elements = []
    this.warnings = []
  }

  warn(msg) {
    if (!this.warnings.includes(msg)) this.warnings.push(msg)
  }

  add(el) {
    if (!catalog.exists(el.article)) {
      this.warn(`Нет блока ${el.article} в каталоге — элемент пропущен`)
      return
    }
    this.elements.push(el)
  }
}

export function generate(st) {
  const out = new Generated()
  posts(st, out)
  ledgers(st, out)
  toeboards(st, out)
  decksAndLadders(st, out)
  diagonals(st, out)
  joinWithoutPosts(out)
  balconyBraces(st, out)
  if (st.lift) applyLift(st.lift, out)
  return out
}

function applyLift(dz, out) {
  for (const e of out.elements) {
    if (e.kind === 'jack') {
      if (e.seg) e.seg[1][2] += dz
      continue
    }
    e.z += dz
    if (e.seg) for (const p of e.seg) p[2] += dz
  }
}

// ---------------------------------------------------------------- стойки ---
export function splitPosts(total) {
  const pieces = new Array(floorDiv(total, POST_PIECE)).fill(POST_PIECE)
  const rest = total % POST_PIECE
  if (rest) pieces.push(rest)
  return pieces
}

function nodeCells(st, il, jl) {
  const seen = new Set()
  const out = []
  for (const di of [-1, 0]) {
    for (const dj of [-1, 0]) {
      for (const c of st.cellsAt(il + di, jl + dj)) {
        if (!seen.has(c) && (il === c.i || il === c.ie) && (jl === c.j || jl === c.je)) {
          seen.add(c)
          out.push(c)
        }
      }
    }
  }
  return out
}

const isWidening = (c) => c.role === 'widening'

function nodeOpen(c, il, jl) {
  return ({ y0: jl === c.j, y1: jl === c.je, x0: il === c.i, x1: il === c.ie })[c.open_side || ''] || false
}

const xEdgeOpen = (c, jl) => (c.open_side === 'y0' && jl === c.j) || (c.open_side === 'y1' && jl === c.je)
const yEdgeOpen = (c, il) => (c.open_side === 'x0' && il === c.i) || (c.open_side === 'x1' && il === c.ie)

function posts(st, out) {
  st.xs.forEach((x, il) => {
    st.ys.forEach((y, jl) => {
      const cells = nodeCells(st, il, jl)
      if (!cells.length) return
      if (cells.every((c) => c.open_side && nodeOpen(c, il, jl))) return
      for (const [bottom, top, ground] of postRuns(cells)) postColumn(st, x, y, bottom, top, ground, out)
    })
  })
}

function postRuns(cells) {
  const runs = []
  for (const c of [...cells].sort((a, b) => a.bottom - b.bottom)) {
    const last = runs[runs.length - 1]
    if (last && c.bottom <= last[1]) {
      last[1] = Math.max(last[1], c.top)
      last[2] = last[2] || c.ground
    } else {
      runs.push([c.bottom, c.top, c.ground])
    }
  }
  return runs
}

function postColumn(st, x, y, bottom, top, ground, out) {
  if (ground) {
    if (st.pads) out.add(new Element(ART_PAD, x, y, 0, 0, 'pad'))
    out.add(new Element(ART_JACK, x, y, 0, 0, 'jack', [[x, y, 0], [x, y, BASE_LEVEL]]))
    out.add(new Element(ART_STARTER, x, y, 0, 0, 'starter'))
  }
  let z = bottom
  splitPosts(top - bottom).forEach((piece, n) => {
    let art = ART_POST(piece)
    if (n === 0 && ground && BOTTOM_POST_SIZES.includes(piece)) art = ART_POST_BOTTOM(piece)
    out.add(new Element(art, x, y, z, 0, 'post', [[x, y, z], [x, y, z + piece]]))
    z += piece
  })
}

// ------------------------------------------------------ рёбра ячеек -------
function mergeRuns(n, cellsOf) {
  const out = []
  let run = null
  for (let k = 0; k < n; k++) {
    const cells = cellsOf(k)
    const key = cells.map((c) => c.uid).sort((a, b) => a - b).join(',')
    if (run !== null && cells.length && run[2] === key) {
      run[1] = k + 1
      continue
    }
    if (run !== null && run[3].length) out.push([[run[0], run[1]], run[3]])
    run = [k, k + 1, key, cells]
  }
  if (run !== null && run[3].length) out.push([[run[0], run[1]], run[3]])
  return out
}

// Рёбра вдоль X: { seg: [a, b], line: jl, cells }
export function xEdges(st) {
  const out = []
  for (let jl = 0; jl < st.ys.length; jl++) {
    const cellsOf = (i) => [
      ...st.cellsAt(i, jl - 1).filter((c) => c.je === jl),
      ...st.cellsAt(i, jl).filter((c) => c.j === jl),
    ]
    for (const [seg, cells] of mergeRuns(st.xs.length - 1, cellsOf)) out.push({ seg, line: jl, cells })
  }
  return out
}

// Рёбра вдоль Y: { line: il, seg: [a, b], cells }
export function yEdges(st) {
  const out = []
  for (let il = 0; il < st.xs.length; il++) {
    const cellsOf = (j) => [
      ...st.cellsAt(il - 1, j).filter((c) => c.ie === il),
      ...st.cellsAt(il, j).filter((c) => c.i === il),
    ]
    for (const [seg, cells] of mergeRuns(st.ys.length - 1, cellsOf)) out.push({ seg, line: il, cells })
  }
  return out
}

function ledgerLevels(st, cells, edgeOpen) {
  if (cells.every((c) => c.open_side && edgeOpen(c))) return []
  const main = cells.filter((c) => !isWidening(c))
  const levels = new Set(main.length ? edgeLedgerLevels(st, main) : [])
  for (const c of cells) {
    if (isWidening(c) && (main.length || !edgeOpen(c))) for (const z of wideningLevels(c)) levels.add(z)
  }
  return sortNum(levels)
}

function edgeLedgerLevels(st, cells) {
  const lo = Math.min(...cells.map(ledgerBottom))
  const hi = Math.max(...cells.map((c) => c.top))
  const levels = new Set()
  for (const c of cells) {
    levels.add(ledgerBottom(c))
    for (const d of c.decks) levels.add(d)
  }
  for (let z = lo; z <= hi; z += NODE_STEP) {
    if (cells.filter((c) => ledgerBottom(c) <= z && z <= c.top).length === 1) levels.add(z)
  }
  return sortNum(levels)
}

function placeX(st, seg, jl, z, artFmt, kind, out) {
  const x0 = st.xs[seg[0]]
  const x1 = st.xs[seg[1]]
  const y = st.ys[jl]
  out.add(new Element(artFmt(x1 - x0), x0, y, z, 0, kind, [[x0, y, z], [x1, y, z]]))
}

function placeY(st, il, seg, z, artFmt, kind, out) {
  const x = st.xs[il]
  const y0 = st.ys[seg[0]]
  const y1 = st.ys[seg[1]]
  out.add(new Element(artFmt(y1 - y0), x, y1, z, 270, kind, [[x, y0, z], [x, y1, z]]))
}

const ENTRANCE_HEIGHT = 2000

function inEntrance(st, seg, jl, z) {
  return st.entrance_bay !== null && jl === st.entrance_line &&
    seg[0] === st.entrance_bay && seg[1] === st.entrance_bay + 1 &&
    z < BASE_LEVEL + ENTRANCE_HEIGHT
}

function ledgers(st, out) {
  for (const { seg, line: jl, cells } of xEdges(st)) {
    for (const z of ledgerLevels(st, cells, (c) => xEdgeOpen(c, jl))) {
      if (inEntrance(st, seg, jl, z)) continue
      placeX(st, seg, jl, z, ART_LEDGER, 'ledger', out)
    }
  }
  for (const { seg, line: il, cells } of yEdges(st)) {
    for (const z of ledgerLevels(st, cells, (c) => yEdgeOpen(c, il))) placeY(st, il, seg, z, ART_LEDGER, 'ledger', out)
  }
}

function toeLevels(cells) {
  const levels = new Set()
  for (const c of cells) {
    if (!c.decks.size) continue
    const z = Math.max(...c.decks)
    const others = cells.filter((o) => o !== c)
    const covered = others.some((o) => [...o.decks].some((d) => Math.abs(d - z) <= DECK_TOLERANCE))
    if (!covered) levels.add(z)
  }
  return sortNum(levels)
}

function toeboards(st, out) {
  for (const { seg, line: jl, cells } of xEdges(st)) {
    if (cells.every((c) => c.open_side && xEdgeOpen(c, jl))) continue
    for (const z of toeLevels(cells)) {
      if (inEntrance(st, seg, jl, z)) continue
      placeX(st, seg, jl, z, ART_TOEBOARD, 'toeboard', out)
    }
  }
  for (const { seg, line: il, cells } of yEdges(st)) {
    if (cells.every((c) => c.open_side && yEdgeOpen(c, il))) continue
    for (const z of toeLevels(cells)) placeY(st, il, seg, z, ART_TOEBOARD, 'toeboard', out)
  }
}

// --------------------------------------------------- настилы, лестницы ----
const hasBuiltinLadder = (article) => catalog.nameOf(article).toLowerCase().includes('лестниц')

function hatch(st, c, z, turned, out) {
  const [x0, y0, x1] = st.cellBox(c)
  const dx = x1 - x0
  const art = ART_HATCH(dx)
  const [ix, iy, rot] = turned ? [x1, y0 + HATCH_WIDTH, 180] : [x0, y0, 0]
  out.add(new Element(art, ix, iy, z, rot, 'hatch', null, [x0, y0, dx, HATCH_WIDTH]))
  if (!hasBuiltinLadder(art)) {
    const [lx, ly, lz] = LADDER_OFFSET
    if (turned) out.add(new Element(ART_LADDER, x1 - lx, y0 + HATCH_WIDTH - ly, z + lz, 270, 'ladder'))
    else out.add(new Element(ART_LADDER, x0 + lx, y0 + ly, z + lz, 90, 'ladder'))
  }
  return HATCH_WIDTH
}

function decksAndLadders(st, out) {
  for (const c of st.allCells()) {
    const [x0, y0, x1, y1] = st.cellBox(c)
    const dx = x1 - x0
    const dy = y1 - y0
    const hatchLevels = c.hatch_decks === null ? c.decks : c.hatch_decks
    const hatchOrder = sortNum(hatchLevels).reverse()
    const floor = c.access ? c.bottom_floor : null
    const groundLadder = floor !== null && (floor.height === 1000 || floor.height === 1500)
    for (const z of sortNum(c.decks)) {
      let used = 0
      if (c.access && hatchLevels.has(z)) {
        if (dy >= HATCH_WIDTH && catalog.exists(ART_HATCH(dx))) {
          const turned = hatchOrder.indexOf(z) % 2 === 1
          used = hatch(st, c, z, turned, out)
        } else {
          out.warn(`Ячейка ${fmtG(dx / 1000)}×${fmtG(dy / 1000)} м: настил с люком не помещается`)
        }
      }
      let y = y0 + used
      const stop = groundLadder && z === floor.deck ? y1 - GROUND_LADDER_PLANKS * PLANK_WIDTH : y1
      while (y + PLANK_WIDTH <= stop) {
        out.add(new Element(ART_PLANK(dx), x0, y, z, 0, 'deck', null, [x0, y, dx, PLANK_WIDTH]))
        y += PLANK_WIDTH
      }
      if (stop === y1 && y < y1) out.warn(`Настил ${fmtG(dx / 1000)} м: остался зазор ${y1 - y} мм по ширине`)
    }
    if (groundLadder) groundLadderFor(st, c, floor, out)
  }
}

function groundLadderFor(st, c, floor, out) {
  const [x0, y0, x1, y1] = st.cellBox(c)
  const dx = x1 - x0
  if (y1 - y0 < GROUND_LADDER_PLANKS * PLANK_WIDTH) {
    out.warn('Ячейка доступа слишком узкая для лестницы с земли')
    return
  }
  for (let k = GROUND_LADDER_PLANKS; k > 0; k--) {
    const y = y1 - k * PLANK_WIDTH
    out.add(new Element(ART_PLANK(dx), x0, y, BASE_LEVEL, 0, 'deck', null, [x0, y, dx, PLANK_WIDTH]))
  }
  const hook = BASE_LEVEL + DECK_STEP
  const [lx, ly, lz] = LADDER_OFFSET
  const stripY0 = y1 - GROUND_LADDER_PLANKS * PLANK_WIDTH
  out.add(new Element(ART_LADDER, x0 + lx - GROUND_LADDER_DX, stripY0 + ly, hook + lz, 90, 'ladder'))
  if (st.exists(c.i - 1, c.j)) {
    out.warn(`Лестница с земли цепляется за внутренний ригель на ${fmtG(hook / 1000)} м — проверьте, что он есть`)
  }
}

// ------------------------------------------------------------ диагонали ---
function liftsFor(cells) {
  const bottom = Math.min(...cells.map((c) => c.bottom))
  const decks = sortNum(new Set(cells.flatMap((c) => [...c.decks])))
  return lifts([bottom, ...decks.filter((d) => d > bottom)])
}

function lifts(marks) {
  const ps = pairs(marks).map(([a, b]) => [a, b - a])
  const full = ps.filter(([, h]) => h === DECK_STEP)
  if (full.length) return full
  return ps.filter(([, h]) => h >= 2 * NODE_STEP).map(([z, h]) => [z, h - (h % NODE_STEP)])
}

function pick(indices) {
  if (!indices.length) return new Set()
  const picked = new Set([indices[0], indices[indices.length - 1]])
  indices.forEach((idx, k) => { if (k % DIAGONAL_EVERY === 0) picked.add(idx) })
  return picked
}

function diagonals(st, out) {
  const edgeLifts = (cells, edgeOpen) => {
    const main = cells.filter((c) => !(c.role === 'widening' || c.role === 'balcony') || !c.open_side)
    if (main.length) {
      const ground = main.filter((c) => c.ground)
      return ground.length === 1 ? [liftsFor(main), ground[0]] : [[], null]
    }
    const wid = cells.filter(isWidening)
    if (wid.length === 1 && !edgeOpen(wid[0])) return [lifts(wideningLevels(wid[0])), wid[0]]
    return [[], null]
  }

  const rows = new Map()
  for (const { seg, line: jl, cells } of xEdges(st)) {
    const [ls, owner] = edgeLifts(cells, (c) => xEdgeOpen(c, jl))
    if (ls.length) {
      if (!rows.has(jl)) rows.set(jl, [])
      rows.get(jl).push([seg, ls, owner.je === jl])
    }
  }
  for (const [jl, edges] of rows) {
    const chosen = pick(edges.map((e) => e[0].join(',')))
    for (const [i, ls, mirrored] of edges) {
      if (!chosen.has(i.join(','))) continue
      const x0 = st.xs[i[0]]
      const x1 = st.xs[i[1]]
      const y = st.ys[jl]
      for (const [z, h] of ls) {
        const art = ART_DIAGONAL(floorDiv(x1 - x0, 10), floorDiv(h, NODE_STEP))
        if (mirrored) out.add(new Element(art, x1, y, z, 180, 'diagonal', [[x1, y, z], [x0, y, z + h]]))
        else out.add(new Element(art, x0, y, z, 0, 'diagonal', [[x0, y, z], [x1, y, z + h]]))
      }
    }
  }

  const cols = new Map()
  for (const { seg, line: il, cells } of yEdges(st)) {
    const [ls, owner] = edgeLifts(cells, (c) => yEdgeOpen(c, il))
    if (ls.length) {
      if (!cols.has(il)) cols.set(il, [])
      cols.get(il).push([seg, ls, owner.ie === il])
    }
  }
  for (const [il, edges] of cols) {
    const chosen = pick(edges.map((e) => e[0].join(',')))
    for (const [j, ls, mirrored] of edges) {
      if (!chosen.has(j.join(','))) continue
      const x = st.xs[il]
      const y0 = st.ys[j[0]]
      const y1 = st.ys[j[1]]
      for (const [z, h] of ls) {
        const art = ART_DIAGONAL(floorDiv(y1 - y0, 10), floorDiv(h, NODE_STEP))
        if (mirrored) out.add(new Element(art, x, y0, z, 90, 'diagonal', [[x, y0, z], [x, y1, z + h]]))
        else out.add(new Element(art, x, y1, z, 270, 'diagonal', [[x, y1, z], [x, y0, z + h]]))
      }
    }
  }
}

// ---------------------------------------- склейка в местах без стоек ------
const JOIN_ART = { ledger: ART_LEDGER, toeboard: ART_TOEBOARD }

function postCover(out) {
  const cover = new Map()
  for (const e of out.elements) {
    if (e.kind === 'post' && e.seg) {
      const k = `${e.x},${e.y}`
      if (!cover.has(k)) cover.set(k, [])
      cover.get(k).push([e.seg[0][2], e.seg[1][2]])
    }
  }
  return cover
}

const hasPost = (cover, x, y, z) => (cover.get(`${x},${y}`) || []).some(([a, b]) => a <= z && z <= b)

function span(e) {
  const [[x0, y0], [x1, y1]] = e.seg
  if (y0 === y1) return ['x', y0, Math.min(x0, x1), Math.max(x0, x1)]
  return ['y', x0, Math.min(y0, y1), Math.max(y0, y1)]
}

function rebuild(e, a, b) {
  const [axis, line] = span(e)
  const length = pyRound(b - a)
  const z = e.z
  let el
  let art
  if (e.kind in JOIN_ART) {
    art = JOIN_ART[e.kind](length)
    el = axis === 'x'
      ? new Element(art, a, line, z, 0, e.kind, [[a, line, z], [b, line, z]])
      : new Element(art, line, b, z, 270, e.kind, [[line, a, z], [line, b, z]])
  } else {
    const h = pyRound(e.seg[1][2] - e.seg[0][2])
    art = ART_DIAGONAL(floorDiv(length, 10), floorDiv(h, NODE_STEP))
    if (axis === 'x') {
      el = e.rot === 0
        ? new Element(art, a, line, z, 0, 'diagonal', [[a, line, z], [b, line, z + h]])
        : new Element(art, b, line, z, 180, 'diagonal', [[b, line, z], [a, line, z + h]])
    } else {
      el = e.rot === 90
        ? new Element(art, line, a, z, 90, 'diagonal', [[line, a, z], [line, b, z + h]])
        : new Element(art, line, b, z, 270, 'diagonal', [[line, b, z], [line, a, z + h]])
    }
  }
  return catalog.exists(art) ? el : null
}

function joinWithoutPosts(out) {
  const cover = postCover(out)
  const groups = new Map()
  const keep = []
  for (const e of out.elements) {
    if (['ledger', 'toeboard', 'diagonal'].includes(e.kind) && e.seg) {
      const [axis, line] = span(e)
      const h = e.seg[1][2] - e.seg[0][2]
      const k = JSON.stringify([e.kind, axis, line, e.z, h, e.rot])
      if (!groups.has(k)) groups.set(k, { axis, line, z: e.z, h, items: [] })
      groups.get(k).items.push(e)
    } else {
      keep.push(e)
    }
  }
  const joined = []
  for (const { axis, line, z, h, items } of groups.values()) {
    items.sort((p, q) => span(p)[2] - span(q)[2])
    let cur = items[0]
    for (const nxt of items.slice(1)) {
      const [, , a0, b0] = span(cur)
      const [, , a1, b1] = span(nxt)
      const [jx, jy] = axis === 'x' ? [b0, line] : [line, b0]
      if (b0 === a1 && !hasPost(cover, jx, jy, z) && !hasPost(cover, jx, jy, z + h)) {
        const merged = rebuild(cur, a0, b1)
        if (merged !== null) {
          cur = merged
          continue
        }
      }
      joined.push(cur)
      cur = nxt
    }
    joined.push(cur)
  }
  out.elements = [...keep, ...joined]
}

// ------------------------------------------------- диагонали балкона ------
const BRACE_HEIGHTS = [2000, 1500, 1000]

function balconyBraces(st, out) {
  const done = new Set()
  for (const c of st.allCells()) {
    if (c.role !== 'balcony' || !c.open_side) continue
    const [x0, y0, x1, y1] = st.cellBox(c)
    const bay = c.open_side === 'y0' || c.open_side === 'y1' ? y1 - y0 : x1 - x0
    const zt = ledgerBottom(c)
    const h = BRACE_HEIGHTS.find((hh) => zt - hh >= BASE_LEVEL &&
      catalog.exists(ART_DIAGONAL(floorDiv(bay, 10), floorDiv(hh, NODE_STEP)))) ?? null
    if (h === null) {
      out.warn(`Балкон: диагональ ${fmtG(bay / 1000)} м под стойкой не помещается — основная конструкция низкая`)
      continue
    }
    const art = ART_DIAGONAL(floorDiv(bay, 10), floorDiv(h, NODE_STEP))
    const z = zt - h
    let lines
    if (c.open_side === 'y1') lines = [x0, x1].map((x) => [x, y1, z, 270, [[x, y1, z], [x, y0, zt]]])
    else if (c.open_side === 'y0') lines = [x0, x1].map((x) => [x, y0, z, 90, [[x, y0, z], [x, y1, zt]]])
    else if (c.open_side === 'x1') lines = [y0, y1].map((y) => [x1, y, z, 180, [[x1, y, z], [x0, y, zt]]])
    else lines = [y0, y1].map((y) => [x0, y, z, 0, [[x0, y, z], [x1, y, zt]]])
    for (const [x, y, zz, rot, seg] of lines) {
      const k = `${x},${y},${rot}`
      if (done.has(k)) continue
      done.add(k)
      out.add(new Element(art, x, y, zz, rot, 'diagonal', seg))
    }
  }
}
