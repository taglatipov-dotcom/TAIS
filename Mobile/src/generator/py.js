// Помощники, чтобы JS-генератор считал так же, как Python-генератор (Backend/tais/generator):
// округление round(), формат {:g}, сравнение кортежей, остаток %, итераторы itertools.

export class SplitError extends Error {
  constructor(message) {
    super(message)
    this.name = 'SplitError'
  }
}

// round(x) / round(x, n) из Python: по точному двоичному значению, ровно половина — к чётному
export function pyRound(x, nd = 0) {
  const p = 10 ** nd
  const m = x * p
  const fl = Math.floor(m)
  if (m - fl === 0.5 && (fl + 0.5) / p === x) {
    const r = fl % 2 === 0 ? fl : fl + 1
    return nd === 0 ? r : r / p
  }
  if (nd === 0) return Math.round(x)
  return Number(x.toFixed(nd))
}

// f"{x:g}": 6 значащих цифр, без лишних нулей
export function fmtG(x) {
  if (x === 0) return '0'
  return String(Number(Number(x).toPrecision(6)))
}

// x % y из Python (знак результата — как у делителя)
export function pyMod(a, b) {
  let m = a % b
  if (m !== 0 && (b < 0) !== (m < 0)) m += b
  return m
}

export const floorDiv = (a, b) => Math.floor(a / b)

// Сравнение как у Python: числа/логические — по значению, списки — поэлементно
export function cmp(a, b) {
  if (Array.isArray(a) && Array.isArray(b)) {
    const n = Math.min(a.length, b.length)
    for (let i = 0; i < n; i++) {
      const c = cmp(a[i], b[i])
      if (c) return c
    }
    return a.length - b.length
  }
  if (typeof a === 'string' && typeof b === 'string') return a < b ? -1 : a > b ? 1 : 0
  const x = Number(a)
  const y = Number(b)
  return x < y ? -1 : x > y ? 1 : 0
}

// min(items, key=...) — первый наименьший
export function minBy(items, key) {
  let best
  let bestKey
  let first = true
  for (const it of items) {
    const k = key(it)
    if (first || cmp(k, bestKey) < 0) {
      best = it
      bestKey = k
      first = false
    }
  }
  if (first) throw new Error('minBy: пустой список')
  return best
}

export const sortNum = (iterable) => Array.from(iterable).sort((a, b) => a - b)
export const sortedBy = (items, key) => [...items].sort((a, b) => cmp(key(a), key(b)))

export const range = (a, b, step = 1) => {
  if (b === undefined) [a, b] = [0, a]
  const out = []
  if (step > 0) for (let v = a; v < b; v += step) out.push(v)
  else for (let v = a; v > b; v += step) out.push(v)
  return out
}

export const zip = (a, b) => a.slice(0, Math.min(a.length, b.length)).map((v, i) => [v, b[i]])
export const pairs = (a) => zip(a, a.slice(1))
export const sum = (a) => a.reduce((s, v) => s + v, 0)

// itertools.combinations
export function* combinations(items, r) {
  const n = items.length
  if (r > n) return
  const idx = range(r)
  yield idx.map((i) => items[i])
  for (;;) {
    let i = r - 1
    while (i >= 0 && idx[i] === i + n - r) i--
    if (i < 0) return
    idx[i]++
    for (let j = i + 1; j < r; j++) idx[j] = idx[j - 1] + 1
    yield idx.map((k) => items[k])
  }
}

export const pad = (n, w) => String(n).padStart(w, '0')
