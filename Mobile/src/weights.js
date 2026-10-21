// Веса элементов для спецификации.
// Порядок: свой вес из настроек приложения → «Веса элементов.csv» из Library → встроенный каталог.
// Свои веса хранятся на телефоне (localStorage WebView — переживает перезапуск приложения).
import csvText from '../../Library/Веса элементов.csv?raw'
import { CATALOG, weightOf as catalogWeight } from './generator/catalog.js'
import { SPEC_GROUPS, defaultSpecName, loadElementsCsv, setOverrides, sortKey } from './generator/spec.js'
import { cmp } from './generator/py.js'

const KEY = 'tais.weights'
const BASE = loadElementsCsv(csvText)

// Вес по умолчанию (без своих настроек)
export const baseWeight = (article) => BASE[article]?.weight ?? catalogWeight(article)

// Все элементы каталога для экрана настроек, в порядке спецификации
export const ITEMS = Object.keys(CATALOG)
  .sort((a, b) => cmp(sortKey(a), sortKey(b)))
  .map((article) => ({
    article,
    name: BASE[article]?.name || defaultSpecName(article),
    group: SPEC_GROUPS[sortKey(article)[0]]?.[0] || 'прочее',
    generator: BASE[article]?.generator ?? false,
    base: baseWeight(article),
  }))

export function loadUserWeights() {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || '{}')
    return v && typeof v === 'object' ? v : {}
  } catch {
    return {}
  }
}

export function saveUserWeights(weights) {
  try {
    localStorage.setItem(KEY, JSON.stringify(weights))
  } catch {
    // хранилище недоступно — веса действуют до закрытия приложения
  }
}

// Передать веса генератору спецификации
export function applyWeights(user) {
  const map = {}
  for (const [art, v] of Object.entries(BASE)) map[art] = { name: v.name, weight: v.weight }
  for (const [art, w] of Object.entries(user || {})) {
    if (typeof w === 'number' && Number.isFinite(w)) map[art] = { name: map[art]?.name ?? null, weight: w }
  }
  setOverrides(map)
}
