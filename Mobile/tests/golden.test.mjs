// Сверка JS-генератора с Python-генератором на эталонах (tests/golden.json).
// Эталоны пересоздаются: python Mobile/tools/make_golden.py (из корня проекта).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { calculate, spec } from '../src/generator/index.js'

const golden = JSON.parse(readFileSync(new URL('./golden.json', import.meta.url), 'utf8'))
const csv = readFileSync(new URL('../../Library/Веса элементов.csv', import.meta.url), 'utf8')
spec.setOverrides(spec.loadElementsCsv(csv))

const TOL = 1e-6

// первое расхождение: путь и значения
function diff(a, b, path = '') {
  if (typeof a === 'number' && typeof b === 'number') {
    return Math.abs(a - b) <= TOL * Math.max(1, Math.abs(b)) ? null : `${path}: ${a} ≠ ${b}`
  }
  if (Array.isArray(b)) {
    if (!Array.isArray(a)) return `${path}: не список`
    if (a.length !== b.length) return `${path}: длина ${a.length} ≠ ${b.length}`
    for (let i = 0; i < b.length; i++) {
      const d = diff(a[i], b[i], `${path}[${i}]`)
      if (d) return d
    }
    return null
  }
  if (b && typeof b === 'object') {
    if (!a || typeof a !== 'object') return `${path}: не объект`
    const keys = new Set([...Object.keys(a), ...Object.keys(b)])
    for (const k of keys) {
      if (!(k in a)) return `${path}.${k}: нет в JS`
      if (!(k in b)) return `${path}.${k}: лишнее в JS`
      const d = diff(a[k], b[k], `${path}.${k}`)
      if (d) return d
    }
    return null
  }
  return a === b ? null : `${path}: ${JSON.stringify(a)} ≠ ${JSON.stringify(b)}`
}

for (const [name, g] of Object.entries(golden)) {
  test(name, () => {
    let res
    let error = null
    try {
      res = calculate(g.items)
    } catch (e) {
      error = e.message
    }
    if (g.error !== undefined) {
      assert.equal(error, g.error)
      return
    }
    assert.equal(error, null)
    const d = diff(res, g.result)
    assert.equal(d, null, d)
  })
}
