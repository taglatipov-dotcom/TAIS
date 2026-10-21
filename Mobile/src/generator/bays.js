// Разбивка длины на пролёты стандартной длины (Backend/tais/generator/bays.py).
// Все размеры — в миллиметрах (целые числа).
import { SplitError, combinations, fmtG, minBy, pairs, range, sum } from './py.js'

export { SplitError }

// Пролёты, для которых есть ригель, стальной настил и бортик
export const BAY_SIZES = [3000, 2500, 2000, 1500, 1000, 750]

export function splitLength(total, breakpoints = null, sizes = BAY_SIZES) {
  if (total <= 0) throw new SplitError('Длина должна быть больше нуля')
  const points = [...new Set([0, total, ...(breakpoints || []).filter((p) => p > 0 && p < total)])]
    .sort((a, b) => a - b)
  const result = []
  for (const [a, b] of pairs(points)) {
    const part = bestSplit(b - a, sizes)
    if (part === null) {
      throw new SplitError(
        `Участок ${fmtG((b - a) / 1000)} м нельзя набрать из пролётов ` +
        `${sizes.map((s) => fmtG(s / 1000)).join(', ')} м`)
    }
    result.push(...part)
  }
  return result
}

function bestSplit(length, sizes) {
  const inf = 10 ** 9
  const step = 250
  if (length % step || sizes.some((s) => s % step)) return null
  const best = new Array(length + 1).fill(inf)
  best[0] = 0
  for (let v = step; v <= length; v += step) {
    for (const s of sizes) {
      if (s <= v && best[v - s] + 1 < best[v]) best[v] = best[v - s] + 1
    }
  }
  const k = best[length]
  if (k >= inf) return null

  const ordered = [...sizes].sort((a, b) => b - a)
  for (const distinct of [1, 2, 3]) {
    const found = search(length, k, ordered, distinct)
    if (found) return found
  }

  const out = []
  let v = length
  while (v) {
    for (const s of ordered) {
      if (s <= v && best[v - s] === best[v] - 1) {
        out.push(s)
        v -= s
        break
      }
    }
  }
  return out
}

function search(length, k, ordered, distinct) {
  const candidates = []
  for (const combo of combinations(ordered, distinct)) {
    for (const counts of compositions(k, distinct)) {
      if (sum(counts.map((c, i) => c * combo[i])) === length) {
        const parts = []
        counts.forEach((c, i) => { for (let n = 0; n < c; n++) parts.push(combo[i]) })
        candidates.push(parts.sort((a, b) => b - a))
      }
    }
  }
  if (!candidates.length) return null
  return minBy(candidates, (p) => p.map((x) => -x))
}

function* compositions(total, parts) {
  if (parts === 1) {
    yield [total]
    return
  }
  for (const first of range(1, total - parts + 2)) {
    for (const rest of compositions(total - first, parts - 1)) yield [first, ...rest]
  }
}

// [2000, 2000] -> [0, 2000, 4000] — координаты стоек
export function cumulative(bays) {
  const out = [0]
  for (const b of bays) out.push(out[out.length - 1] + b)
  return out
}
