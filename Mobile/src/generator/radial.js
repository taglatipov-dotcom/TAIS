// Радиальные леса — замкнутое кольцо вокруг объекта (Backend/tais/generator/radial.py).
// Лента фасадных лесов → rules.generate → сгибание в кольцо, ригели-вставки снаружи,
// планки в клиньях между ячейками.
import * as catalog from './catalog.js'
import { BAY_SIZES, cumulative, splitLength } from './bays.js'
import { buildGroup, makeInput, toMm } from './constructions.js'
import { Element, wideningLevels } from './model.js'
import { ART_LEDGER, ART_TOEBOARD, generate } from './rules.js'
import { SplitError, cmp, combinations, fmtG, minBy, pairs, pad, pyMod, pyRound, range, sortNum, sum } from './py.js'

const MIN_CELLS = 4
const DEV_MAX = 50
const HOLE_OK = 150
const SAG_MAX = 300
const EPS = 1e-6
const LEDGER_SIZES = sortNum(Object.keys(catalog.CATALOG).filter((a) => a.startsWith('S11013.')).map((a) => Number(a.split('.')[1])))
const RAD_TO_DEG = 180.0 / Math.PI
const degrees = (r) => RAD_TO_DEG * r

// ------------------------------------------------------------ геометрия ---
export function ringRadius(cells) {
  const lmax = Math.max(...cells)
  const excess = (r) => sum(cells.map((c) => 2 * Math.asin(Math.min(1.0, c / (2 * r))))) - 2 * Math.PI
  let lo = lmax / 2
  let hi = sum(cells)
  if (excess(lo) < 0) throw new SplitError('Радиальные леса: ячейки слишком разной длины — кольцо не замыкается')
  for (let n = 0; n < 60; n++) {
    const mid = (lo + hi) / 2
    if (excess(mid) > 0) lo = mid
    else hi = mid
  }
  return (lo + hi) / 2
}

const centralAngles = (cells, r) => cells.map((c) => 2 * Math.asin(Math.min(1.0, c / (2 * r))))

function jointAngles(cells, r) {
  const a = centralAngles(cells, r)
  return range(cells.length).map((k) => (a[(k - 1 + a.length) % a.length] + a[k]) / 2)
}

const nearestLedger = (gap) => minBy(LEDGER_SIZES, (s) => [Math.abs(s - gap), s])

function gapTable(sections, offsets) {
  const r = ringRadius(sections)
  const out = []
  jointAngles(sections, r).forEach((phi, k) => {
    for (const d of offsets) {
      const g = 2 * d * Math.sin(phi / 2)
      out.push([k, d, g, nearestLedger(g)])
    }
  })
  return out
}

function group(cells, k) {
  const out = []
  for (let i = 0; i < cells.length; i += k) out.push(sum(cells.slice(i, i + k)))
  return out
}

function sagitta(sections) {
  const r = ringRadius(sections)
  return r * (1 - Math.cos(Math.max(...centralAngles(sections, r)) / 2))
}

function score(cells, offsets) {
  const out = []
  const n = cells.length
  for (let k = 1; k <= Math.floor(n / MIN_CELLS); k++) {
    if (n % k) continue
    const sections = group(cells, k)
    let dev
    let sag
    try {
      dev = Math.max(...gapTable(sections, offsets).map(([, , g, s]) => Math.abs(g - s)))
      sag = sagitta(sections)
    } catch (e) {
      if (e instanceof SplitError) continue
      throw e
    }
    const key = dev <= DEV_MAX && sag <= SAG_MAX
      ? [0, new Set(cells).size !== 1, -Math.min(...cells), k, dev]
      : [1, sag > SAG_MAX, dev, k]
    out.push([key, cells, k])
  }
  return out
}

export function chooseCells(length, offsets) {
  let scored = []
  for (const s of BAY_SIZES) {
    if (length % s === 0 && length / s >= MIN_CELLS) scored = scored.concat(score(new Array(length / s).fill(s), offsets))
  }
  const best = () => scored.reduce((m, t) => (cmp(t, m) < 0 ? t : m))
  if (!scored.length || best()[0][0] !== 0) {
    const cands = []
    for (const [a, b] of combinations(BAY_SIZES, 2)) {
      for (let ca = 1; ca <= Math.floor(length / a); ca++) {
        const rest = length - ca * a
        if (rest > 0 && rest % b === 0 && ca + rest / b >= MIN_CELLS) cands.push(interleave(a, ca, b, rest / b))
      }
    }
    try {
      const mixed = splitLength(length)
      if (mixed.length >= MIN_CELLS && !cands.some((c) => cmp(c, mixed) === 0)) cands.push(mixed)
    } catch (e) {
      if (!(e instanceof SplitError)) throw e
    }
    for (const c of cands) scored = scored.concat(score(c, offsets))
  }
  if (!scored.length) {
    throw new SplitError(
      `Радиальные леса: длину ${fmtG(length / 1000)} м нельзя набрать хотя бы из ${MIN_CELLS} ячеек ` +
      `${BAY_SIZES.map((s) => fmtG(s / 1000)).join(', ')} м`)
  }
  const [, cells, k] = minBy(scored, (t) => t[0])
  return [cells, k]
}

function interleave(a, ca, b, cb) {
  const out = []
  let acc = 0
  for (let n = 0; n < ca + cb; n++) {
    acc += ca
    if (acc >= ca + cb) {
      acc -= ca + cb
      out.push(a)
    } else {
      out.push(b)
    }
  }
  return out
}

// --------------------------------------------------------- сгибание ленты -
class Ring {
  constructor(cells, xs, yIn) {
    this.cells = cells
    this.xs = xs
    this.y_in = yIn
    this.n = cells.length
    this.r = ringRadius(cells)
    const alpha = centralAngles(cells, this.r)
    let b = -Math.PI / 2 - alpha[0] / 2
    this.p = []
    for (let k = 0; k < this.n; k++) {
      this.p.push([this.r * Math.cos(b), this.r * Math.sin(b)])
      b += alpha[k]
    }
    this.p.push(this.p[0])
    this.u = cells.map((c, k) => {
      const [x0, y0] = this.p[k]
      const [x1, y1] = this.p[k + 1]
      return [(x1 - x0) / c, (y1 - y0) / c]
    })
    this.turn = jointAngles(cells, this.r)
  }

  angle(k) {
    const [ux, uy] = this.u[k]
    return degrees(Math.atan2(uy, ux))
  }

  tf(k, x, y) {
    const [px, py] = this.p[k]
    const [ux, uy] = this.u[k]
    const a = x - this.xs[k]
    const d = this.y_in - y
    return [px + a * ux + d * uy, py + a * uy - d * ux]
  }

  move(e, k) {
    const [x, y] = this.tf(k, e.x, e.y)
    const seg = e.seg ? e.seg.map((p) => [...this.tf(k, p[0], p[1]), p[2]]) : null
    let box = null
    let poly = null
    if (e.box) {
      const [bx, by, dx, dy] = e.box
      poly = [[bx, by], [bx + dx, by], [bx + dx, by + dy], [bx, by + dy]].map(([cx, cy]) => this.tf(k, cx, cy))
      const px = poly.map((q) => q[0])
      const py = poly.map((q) => q[1])
      box = [Math.min(...px), Math.min(...py), Math.max(...px) - Math.min(...px), Math.max(...py) - Math.min(...py)]
    }
    const rot = pyRound(pyMod(e.rot + this.angle(k), 360), 6)
    return new Element(e.article, x, y, e.z, rot, e.kind, seg, box, poly)
  }
}

function line(e) {
  if (e.seg) {
    const [[x0, y0], [x1, y1]] = e.seg
    if (Math.abs(x0 - x1) > EPS) return [(x0 + x1) / 2, 'x']
    if (Math.abs(y0 - y1) > EPS) return [x0, 'y']
    return [x0, 'point']
  }
  if (e.box) return [e.box[0] + e.box[2] / 2, 'x']
  return [e.x, 'point']
}

function owners(ring, e) {
  const { xs, n } = ring
  const [rx, kind] = line(e)
  for (let k = 0; k < n; k++) if (xs[k] + EPS < rx && rx < xs[k + 1] - EPS) return [k]
  const j = minBy(range(n + 1), (k) => Math.abs(xs[k] - rx))
  if (kind === 'x') return [Math.min(j, n - 1)]
  if (kind === 'y') return j === 0 || j === n ? [] : [j - 1, j]
  const inner = Math.abs(e.y - ring.y_in) < EPS
  if (j === n) return inner ? [] : [n - 1]
  if (j === 0) return [0]
  return inner ? [j] : [j - 1, j]
}

const r3 = (v) => pyRound(v, 3)

function bend(st, elements, k, deckWidth = null) {
  const xs = st.xs.filter((_, i) => i % k === 0)
  const ring = new Ring(pairs(xs).map(([a, b]) => b - a), xs, st.ys[st.ys.length - 1])
  const n = ring.n
  const local = []
  for (const e of elements) for (const kk of owners(ring, e)) local.push([kk, e])
  for (const e of elements) {
    const [rx, kind] = line(e)
    if (kind === 'y' && e.kind === 'ledger' && Math.abs(rx - xs[1]) < EPS) {
      for (const [kk, x] of [[0, xs[0]], [n - 1, xs[n]]]) {
        local.push([kk, new Element(e.article, x, e.y, e.z, e.rot, e.kind,
          e.seg.map((p) => [x, p[1], p[2]]), e.box, e.poly)])
      }
    }
  }

  const levels = new Map()
  for (const [kk, e] of local) {
    if ((e.kind === 'ledger' || e.kind === 'toeboard') && line(e)[1] === 'x') {
      const key = `${e.kind}|${kk}|${r3(e.seg[0][1])}`
      if (!levels.has(key)) levels.set(key, new Set())
      levels.get(key).add(e.z)
    }
  }

  const out = local.map(([kk, e]) => ring.move(e, kk))
  const gaps = []
  for (let j = 0; j < n; j++) {
    const prev = pyMod(j - 1, n)
    for (const yl of st.ys.slice(0, -1)) {
      const [ax, ay] = ring.tf(prev, xs[prev + 1], yl)
      const [bx, by] = ring.tf(j, xs[j], yl)
      const gap = Math.hypot(bx - ax, by - ay)
      if (gap < 1) continue
      const size = nearestLedger(gap)
      const dx = (bx - ax) / gap
      const dy = (by - ay) / gap
      const sx = ax + dx * (gap - size) / 2
      const sy = ay + dy * (gap - size) / 2
      const rot = pyRound(pyMod(degrees(Math.atan2(dy, dx)), 360), 6)
      gaps.push({ joint: j, offset: pyRound(st.ys[st.ys.length - 1] - yl), gap: pyRound(gap), ledger: size, dev: pyRound(gap - size) })
      const key = r3(yl)
      for (const [kind, fmt] of [['ledger', ART_LEDGER], ['toeboard', ART_TOEBOARD]]) {
        const zs = new Set([...(levels.get(`${kind}|${prev}|${key}`) || []), ...(levels.get(`${kind}|${j}|${key}`) || [])])
        for (const z of sortNum(zs)) {
          out.push(new Element(fmt(size), sx, sy, z, rot, kind, [[sx, sy, z], [sx + dx * size, sy + dy * size, z]]))
        }
      }
    }
  }
  if (deckWidth) wedgePlanks(st, ring, local, deckWidth, out, gaps)
  return [out, gaps, ring]
}

// ------------------------------------------------- планки в клиньях ------
const PLANK_WIDTH = 250
const PLANK_SIZES = sortNum(Object.keys(catalog.CATALOG).filter((a) => a.startsWith('U00141.')).map((a) => Number(a.split('.')[1])))
const ART_PLANK_GAP = (n) => `U00141.${pad(n, 4)}`
const PLANK_BEARING = 100
const POST_CLEAR = 60

function wedgePlanks(st, ring, local, deckWidth, out, gaps) {
  const yIn = st.ys[st.ys.length - 1]
  const lines = sortNum(st.ys.map((y) => yIn - y).filter((d) => d > 0 && d <= deckWidth))
  const n = ring.n
  const decks = new Map()
  for (const [k, e] of local) {
    if ((e.kind === 'deck' || e.kind === 'hatch') && e.box) {
      if (!decks.has(k)) decks.set(k, new Set())
      decks.get(k).add(e.z)
    }
  }
  const holes = new Map()
  for (let j = 0; j < n; j++) {
    const prev = pyMod(j - 1, n)
    const a = decks.get(prev) || new Set()
    const b = decks.get(j) || new Set()
    const zs = sortNum([...a].filter((z) => b.has(z)))
    if (!zs.length) continue
    const half = ring.turn[j] / 2
    const tg = Math.tan(half)
    const [ux0, uy0] = ring.u[prev]
    const [ux1, uy1] = ring.u[j]
    let mx = uy0 + uy1
    let my = -ux0 - ux1
    const norm = Math.hypot(mx, my)
    mx /= norm
    my /= norm
    const tx = my
    const ty = -mx
    const rot = pyRound(pyMod(degrees(Math.atan2(ty, tx)), 360), 6)
    const [px, py] = ring.p[j]
    const [bands, hole] = planBands(lines.map((d) => d * Math.cos(half)), tg)
    holes.set(j, hole)
    for (const [s0, size] of bands) {
      const cx = px + mx * s0 - tx * size / 2
      const cy = py + my * s0 - ty * size / 2
      const corners = [[cx, cy], [cx + tx * size, cy + ty * size],
        [cx + tx * size + mx * PLANK_WIDTH, cy + ty * size + my * PLANK_WIDTH],
        [cx + mx * PLANK_WIDTH, cy + my * PLANK_WIDTH]]
      const xs_ = corners.map((c) => c[0])
      const ys_ = corners.map((c) => c[1])
      const box = [Math.min(...xs_), Math.min(...ys_), Math.max(...xs_) - Math.min(...xs_), Math.max(...ys_) - Math.min(...ys_)]
      for (const z of zs) {
        out.push(new Element(ART_PLANK_GAP(size), cx, cy, z, rot, 'deck', null, box, corners.map((c) => [...c])))
      }
    }
  }
  for (const g of gaps) g.hole = pyRound(holes.get(g.joint) || 0)
}

function planBands(linesS, tg) {
  const bands = []
  let hole = 0.0
  const sOut = linesS[linesS.length - 1]
  const obstacles = [0.0, ...linesS]
  for (let k = obstacles.length - 1; k > 0; k--) {
    const lo = obstacles[k - 1]
    const hi = obstacles[k]
    let top = hi - POST_CLEAR
    const bottomLimit = lo + POST_CLEAR
    for (;;) {
      const need = 2 * top * tg + 2 * PLANK_BEARING
      const size = PLANK_SIZES.find((p) => p >= need) ?? null
      if (size === null) {
        hole = Math.max(hole, 2 * top * tg)
        break
      }
      if (hi === sOut) {
        const over = (size / 2 - sOut * tg) * tg
        if (over > sOut - top + 0.5) {
          top = sOut - over
          continue
        }
      }
      const bottom = top - PLANK_WIDTH
      if (bottom < bottomLimit || (lo === 0.0 && bottom < size / 2 * tg)) {
        hole = Math.max(hole, 2 * top * tg)
        break
      }
      bands.push([bottom, size])
      top = bottom
    }
  }
  return [bands, hole]
}

function normalize(elements) {
  const pts = []
  for (const e of elements) {
    pts.push([e.x, e.y])
    for (const p of e.seg || []) pts.push([p[0], p[1]])
    for (const p of e.poly || []) pts.push([p[0], p[1]])
  }
  const mx = Math.min(...pts.map((p) => p[0]))
  const my = Math.max(...pts.map((p) => p[0]))
  const nx = Math.min(...pts.map((p) => p[1]))
  const ny = Math.max(...pts.map((p) => p[1]))
  for (const e of elements) {
    e.x = r3(e.x - mx)
    e.y = r3(e.y - nx)
    if (e.seg) e.seg = e.seg.map((p) => [r3(p[0] - mx), r3(p[1] - nx), p[2]])
    if (e.poly) {
      e.poly = e.poly.map((p) => [r3(p[0] - mx), r3(p[1] - nx)])
      const [bx, by, dx, dy] = e.box
      e.box = [r3(bx - mx), r3(by - nx), r3(dx), r3(dy)]
    }
  }
  return [my - mx, ny - nx]
}

// ------------------------------------------------------------- расчёт -----
function build(inp) {
  const L = toMm(inp.length)
  const W = toMm(inp.width)
  if (L % 250) throw new SplitError('Радиальные леса: длина должна быть кратна 0.25 м')
  const mainYs = cumulative(splitLength(W))
  const offsets = mainYs.slice(0, -1).map((y) => W - y)
  const wid = []
  if (inp.widening) {
    if (!inp.widening_width || inp.widening_width <= 0) throw new SplitError('Радиальные леса: укажите вынос уширения')
    offsets.push(...cumulative(splitLength(toMm(inp.widening_width))).slice(1).map((v) => W + v))
    wid.push(makeInput({
      kind: 'widening', length: inp.length, width: inp.widening_width,
      height: inp.widening_height || inp.height, pads: inp.pads, attach_to: 1, side: 'y0', offset: 0.0,
    }))
  }
  const [cells, k] = chooseCells(L, offsets)
  const main = makeInput({
    kind: 'facade', length: inp.length, width: inp.width, height: inp.height,
    intermediate_decks: inp.intermediate_decks, entrance: inp.entrance, pads: inp.pads,
  })
  const [st, notes0] = buildGroup(main, wid, cells)
  const gen = generate(st)
  const [elements, gaps, ring] = bend(st, gen.elements, k, W)
  const notes = notes0.map((w) => (w.startsWith('Входная группа закрыта уширением')
    ? 'Входная группа закрыта уширением — перенесена на внутреннюю сторону кольца (к объекту), проверьте проход'
    : w))
  const warnings = [...notes, ...gen.warnings, ...gapWarnings(gaps)]
  if (k > 1) {
    warnings.push(`Радиальные леса: поворот через ${k} ячейки — прямые участки ` +
      `${sortNum(new Set(ring.cells)).map((s) => fmtG(s / 1000)).join('/')} м, середина участка ` +
      `ближе к объекту на ${(sagitta(ring.cells) / 1000).toFixed(2)} м, чем стыки`)
  }
  return [st, elements, gaps, ring, warnings]
}

function gapWarnings(gaps) {
  const out = []
  const seen = new Set()
  for (const g of gaps) {
    const key = `${g.offset},${g.gap},${g.ledger}`
    if (seen.has(key) || g.dev === 0) continue
    seen.add(key)
    out.push(`Радиальные леса: наружный зазор между ячейками ${fmtG(g.gap / 1000)} м ` +
      `(в ${fmtG(g.offset / 1000)} м от внутренней стороны) — вставка ригелем ` +
      `${fmtG(g.ledger / 1000)} м, разница ${Math.abs(g.dev)} мм ` +
      `(${g.dev > 0 ? 'ригель короче' : 'ригель длиннее'}) — проверьте на месте`)
  }
  const hole = Math.max(0, ...gaps.map((g) => g.hole || 0))
  if (hole > HOLE_OK) {
    out.push('Радиальные леса: клин между ячейками перекрыт планками U00141, но у стоек остаётся ' +
      `щель до ${fmtG(hole / 1000)} м — проверьте на месте`)
  }
  return out
}

export function runRadial(inp, specification) {
  const [st, elements, gaps, ring, warnings] = build(inp)
  const [sizeX, sizeY] = normalize(elements)
  const cells = st.allCells()
  const widCells = cells.filter((c) => c.role === 'widening')
  const turns = sortNum(new Set(ring.turn.map((a) => pyRound(degrees(a), 2))))
  const inserts = [...new Map(gaps.map((g) => [`${g.ledger},${g.offset}`, [g.ledger, g.offset]])).values()]
    .sort(cmp)
  return {
    input: {
      kind: inp.kind, length: inp.length, width: inp.width, height: inp.height,
      intermediate_decks: inp.intermediate_decks, entrance: inp.entrance, pads: inp.pads,
      widening: inp.widening, widening_width: inp.widening_width, widening_height: inp.widening_height,
    },
    grid: {
      xs: [0, pyRound(sizeX)],
      ys: [0, pyRound(sizeY)],
      bays_x: pairs(st.xs).map(([a, b]) => b - a),
      bays_y: pairs(st.ys).map(([a, b]) => b - a),
      top: st.top + st.lift,
      decks: sortNum(new Set(cells.flatMap((c) => [...c.decks]))).map((z) => z + st.lift),
      lift: st.lift,
      widening_levels: sortNum(new Set(widCells.flatMap((c) => wideningLevels(c).map((z) => z + st.lift)))),
      radial: {
        cells: st.xs.length - 1,
        sections: ring.n,
        per_section: Math.floor((st.xs.length - 1) / ring.n),
        radius: pyRound(ring.r),
        turn: turns,
        inserts,
        max_dev: Math.max(0, ...gaps.map((g) => Math.abs(g.dev))),
      },
    },
    area: {
      formula: `${fmtG(inp.length)} х ${fmtG(inp.height)}`,
      value: pyRound(inp.length * inp.height, 3),
    },
    elements: elements.map((e) => e.toDict()),
    spec: specification(elements),
    warnings,
  }
}
