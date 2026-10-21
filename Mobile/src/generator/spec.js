// Спецификация: количество по артикулам, наименования и веса, порядок строк
// (Backend/tais/generator/spec.py). Веса: свои (настройки приложения) → файл «Веса элементов.csv»
// → встроенный каталог.
import * as catalog from './catalog.js'
import { cmp, pyRound } from './py.js'

export const SPEC_GROUPS = [
  ['подкладки', ['U22061']],
  ['домкраты', ['U22011']],
  ['стартовые элементы', ['S01032']],
  ['стойки', ['S01022', 'S01062', 'S01081', 'S01091']],
  ['ригели', ['S11013', 'S11041']],
  ['диагонали', ['S02012', 'S02032']],
  ['настилы', ['U00221', 'U00281', 'U00141', 'U00161']],
  ['бортики', ['U10012', 'U10071']],
  ['лестницы', ['U07021', 'U07041']],
]

// артикул -> { name: string|null, weight: number|null }
let overrides = {}

export function setOverrides(map) {
  overrides = map || {}
}

function groupIndex(article) {
  const prefix = article.split('.')[0]
  const n = SPEC_GROUPS.findIndex(([, prefixes]) => prefixes.includes(prefix))
  return n < 0 ? SPEC_GROUPS.length : n
}

export const sortKey = (article) => [groupIndex(article), article]

export function parseWeight(text) {
  const t = String(text ?? '').trim().replace(/,/g, '.').replace(/ /g, '')
  if (!t) return null
  const v = Number(t)
  return Number.isFinite(v) ? v : null
}

// CSV через «;» (кавычки — как у csv.reader)
export function parseCsv(text, delimiter = ';') {
  const rows = []
  let row = []
  let cell = ''
  let quoted = false
  const src = text.replace(/^﻿/, '')
  for (let i = 0; i < src.length; i++) {
    const ch = src[i]
    if (quoted) {
      if (ch === '"' && src[i + 1] === '"') {
        cell += '"'
        i++
      } else if (ch === '"') {
        quoted = false
      } else {
        cell += ch
      }
    } else if (ch === '"' && cell === '') {
      quoted = true
    } else if (ch === delimiter) {
      row.push(cell)
      cell = ''
    } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && src[i + 1] === '\n') i++
      row.push(cell)
      rows.push(row)
      row = []
      cell = ''
    } else {
      cell += ch
    }
  }
  if (cell !== '' || row.length) {
    row.push(cell)
    rows.push(row)
  }
  return rows
}

// «Веса элементов.csv» -> { артикул: { name, weight, generator } }
export function loadElementsCsv(text) {
  const out = {}
  const rows = parseCsv(text)
  if (!rows.length) return out
  const head = rows[0].map((h) => h.trim().toLowerCase())
  const col = (...names) => {
    const i = head.findIndex((h) => names.some((n) => h.includes(n)))
    return i < 0 ? null : i
  }
  const iArt = col('артикул')
  const iName = col('наименование в спецификации')
  const iBlock = col('наименование')
  const iW = col('вес')
  const iGen = col('ставит генератор')
  if (iArt === null) return out
  for (const r of rows.slice(1)) {
    if (iArt >= r.length || !/^[SU]\d{5}\.\d{4}$/.test(r[iArt].trim())) continue
    const name = iName !== null && iName < r.length && r[iName].trim() ? r[iName].trim() : null
    const weight = iW !== null && iW < r.length ? parseWeight(r[iW]) : null
    out[r[iArt].trim()] = {
      name,
      weight,
      block: iBlock !== null && iBlock < r.length ? r[iBlock].trim() : null,
      generator: iGen !== null && iGen < r.length ? r[iGen].trim().toLowerCase() === 'да' : null,
    }
  }
  return out
}

// «Ригель S (2.0м)» -> «S3 Ригель (2.0м)», «Элемент стартовый S» -> «S2 Элемент стартовый»
export function defaultSpecName(article) {
  let name = catalog.nameOf(article)
  if (name === article) return name
  let prefix
  if (article.startsWith('S01') || article.startsWith('S02')) prefix = 'S2'
  else if (article.startsWith('S11')) prefix = 'S3'
  else if (article.startsWith('U10')) prefix = 'U2'
  else if (article.startsWith('U')) prefix = 'U1'
  else prefix = ''
  name = name.replace(/\s+S(?=\s|$)/g, '').trim()
  name = name.replace(/градусов\(/g, 'градусов (')
  return `${prefix} ${name}`.trim()
}

export const specName = (article) => overrides[article]?.name || defaultSpecName(article)

export function weight(article) {
  const w = overrides[article]?.weight
  return w !== null && w !== undefined ? w : catalog.weightOf(article)
}

// Спецификация по списку артикулов (по одному на каждую вставку блока)
export function build(articles) {
  const counts = new Map()
  for (const a of articles) counts.set(a, (counts.get(a) || 0) + 1)
  const rows = []
  const unknown = []
  let total = 0.0
  const order = [...counts.keys()].sort((a, b) => cmp(sortKey(a), sortKey(b)))
  for (const art of order) {
    const w = weight(art)
    const qty = counts.get(art)
    if (w === null) unknown.push(art)
    else total += w * qty
    rows.push({
      article: art,
      name: specName(art),
      qty,
      unit_weight: w,
      total_weight: w !== null ? pyRound(w * qty, 2) : null,
    })
  }
  return { rows, total_weight: pyRound(total, 2), unknown_weights: unknown.length, unknown_articles: unknown }
}
