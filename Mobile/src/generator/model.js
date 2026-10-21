// Модель конструкции: сетка стоек + ячейки с настилами (Backend/tais/generator/model.py).
import { range, sortNum } from './py.js'

export const BASE_LEVEL = 105 // отметка первого узла над нулём, мм
export const NODE_STEP = 500 // шаг узлов по высоте, мм
export const DECK_STEP = 2000 // шаг между рабочими настилами, мм
export const TOP_FLOOR = 1500 // последний этаж над верхним настилом, мм
export const MIN_HEIGHT = 1500 // минимальная высота конструкции по акту, мм

let UID = 0

export class Cell {
  constructor({
    i, j, decks = new Set(), top = 0, bottom = BASE_LEVEL, ground = true, access = false,
    hatch_decks = null, bottom_floor = null, role = 'tower', open_side = null, i_end = null, j_end = null,
  }) {
    Object.assign(this, { i, j, decks, top, bottom, ground, access, hatch_decks, bottom_floor, role, open_side, i_end, j_end })
    this.uid = ++UID // вместо id() в Python
  }

  get ie() { return this.i_end === null ? this.i + 1 : this.i_end }
  get je() { return this.j_end === null ? this.j + 1 : this.j_end }
}

// Нижний ряд ригелей ячейки (у балкона — под настилом)
export function ledgerBottom(c) {
  if (c.role === 'balcony' && c.decks.size) return Math.min(...c.decks)
  return c.bottom
}

// Ригели уширения: от нижнего узла через 2 м и на верху стоек
export function wideningLevels(c) {
  return sortNum(new Set([...range(c.bottom, c.top, DECK_STEP), c.top]))
}

const key = (i, j) => `${i},${j}`

// Словарь ячеек по месту плана (i, j); порядок вставки сохраняется, как у dict
export class CellMap {
  constructor() { this.m = new Map() }
  get(i, j) { return this.m.get(key(i, j)) }
  set(i, j, c) { this.m.set(key(i, j), c) }
  has(i, j) { return this.m.has(key(i, j)) }
  values() { return [...this.m.values()] }
}

export class Structure {
  constructor({ xs, ys, kind = 'tower', lift = 0, entrance_bay = null, entrance_line = 0, pads = false }) {
    Object.assign(this, { xs, ys, kind, lift, entrance_bay, entrance_line, pads })
    this.cells = new CellMap()
    this.upper = new CellMap() // балкон над уширением
  }

  cellsAt(i, j) {
    return [this.cells.get(i, j), this.upper.get(i, j)].filter((c) => c !== undefined)
  }

  allCells() {
    const out = []
    const seen = new Set()
    for (const c of [...this.cells.values(), ...this.upper.values()]) {
      if (!seen.has(c)) {
        seen.add(c)
        out.push(c)
      }
    }
    return out
  }

  cellBox(c) { return [this.xs[c.i], this.ys[c.j], this.xs[c.ie], this.ys[c.je]] }
  exists(i, j) { return this.cells.has(i, j) }
  get length() { return this.xs[this.xs.length - 1] - this.xs[0] }
  get width() { return this.ys[this.ys.length - 1] - this.ys[0] }
  get top() {
    const cells = this.allCells()
    return cells.length ? Math.max(...cells.map((c) => c.top)) : 0
  }
}

// Одна вставка блока
export class Element {
  constructor(article, x, y, z, rot = 0, kind = '', seg = null, box = null, poly = null) {
    Object.assign(this, { article, x, y, z, rot, kind, seg, box, poly })
  }

  toDict() {
    const d = { article: this.article, x: this.x, y: this.y, z: this.z, rot: this.rot, kind: this.kind }
    if (this.seg !== null) d.seg = this.seg
    if (this.box !== null) d.box = [...this.box]
    if (this.poly !== null) d.poly = this.poly
    return d
  }
}
