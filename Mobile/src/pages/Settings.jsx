import { useMemo, useState } from 'react'
import { App, Button, Input, InputNumber, Popconfirm, Segmented } from 'antd'
import { SearchOutlined, UndoOutlined } from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'
import { ITEMS } from '../weights.js'
import { useStore } from '../App.jsx'

const parser = (v) => (v ?? '').replace(/\s/g, '').replace(',', '.')
const kg = (v) => v.toLocaleString('ru-RU')

// Одна строка: наименование, артикул, вес. Пустое поле — вес по умолчанию.
function WeightRow({ item, value, onChange }) {
  const changed = value !== undefined
  const shown = changed ? value : item.base
  // пока поле в фокусе — черновик; сохраняем по выходу из поля (иначе пустое поле сразу
  // подменялось бы весом по умолчанию)
  const [draft, setDraft] = useState(undefined)
  const commit = () => {
    if (draft === undefined) return
    onChange(item.article, draft === null ? undefined : draft)
    setDraft(undefined)
  }
  return (
    <div className="spec-row">
      <div className="min-w-0 flex-1">
        <div className="font-medium leading-snug">{item.name}</div>
        <div className="text-[12px] text-[#8e8e93]">
          {item.article}
          {changed && item.base != null && <> · по умолчанию {kg(item.base)} кг</>}
          {shown == null && <span className="text-[#ff9500]"> · вес не указан</span>}
        </div>
      </div>
      <div className="flex items-center gap-1">
        <InputNumber value={draft !== undefined ? draft : (shown ?? null)} min={0} max={1000} step={0.01}
          inputMode="decimal" parser={parser} placeholder="кг" controls={false}
          className={`!w-[92px] ${changed ? 'weight-changed' : ''}`}
          onChange={setDraft} onBlur={commit} onPressEnter={(e) => e.target.blur()} />
        <Button type="text" size="small" icon={<UndoOutlined />} disabled={!changed}
          onClick={() => onChange(item.article, undefined)} aria-label="Вернуть вес по умолчанию" />
      </div>
    </div>
  )
}

export default function Settings() {
  const { message } = App.useApp()
  const { weights, setWeights } = useStore()
  const [params] = useSearchParams()
  const [filter, setFilter] = useState(params.get('unknown') ? 'unknown' : 'generator')
  const [query, setQuery] = useState('')

  const onChange = (article, v) => {
    const next = { ...weights }
    const base = ITEMS.find((i) => i.article === article)?.base
    // пустое значение или совпадающее с умолчанием — свой вес не храним
    if (v === undefined || v === null || v === base) delete next[article]
    else next[article] = v
    setWeights(next)
  }

  const list = useMemo(() => {
    const q = query.trim().toLowerCase()
    return ITEMS.filter((i) => {
      if (filter === 'generator' && !i.generator) return false
      if (filter === 'unknown' && (weights[i.article] ?? i.base) != null) return false
      return !q || i.article.toLowerCase().includes(q) || i.name.toLowerCase().includes(q)
    })
  }, [filter, query, weights])

  const groups = useMemo(() => {
    const out = []
    for (const i of list) {
      if (!out.length || out[out.length - 1].name !== i.group) out.push({ name: i.group, items: [] })
      out[out.length - 1].items.push(i)
    }
    return out
  }, [list])

  const changedCount = Object.keys(weights).length
  const missing = ITEMS.filter((i) => i.generator && (weights[i.article] ?? i.base) == null).length

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1 className="page-title">Настройки</h1>
          <p className="page-subtitle">Вес одного изделия для спецификации, кг</p>
        </div>
      </header>

      <section className="card mb-3 flex items-center gap-3">
        <div className="min-w-0 flex-1 text-[13px] leading-snug text-[#636366]">
          Изменено: <b>{changedCount}</b>
          {missing > 0 && <> · без веса (ставит генератор): <b className="text-[#ff9500]">{missing}</b></>}
          <div className="text-[#8e8e93]">Веса хранятся на этом телефоне.</div>
        </div>
        <Popconfirm title="Вернуть все веса по умолчанию?" okText="Вернуть" cancelText="Отмена"
          disabled={!changedCount}
          onConfirm={() => { setWeights({}); message.success('Веса по умолчанию') }}>
          <Button disabled={!changedCount}>Сбросить</Button>
        </Popconfirm>
      </section>

      <div className="sticky-tools">
        <Input allowClear prefix={<SearchOutlined className="text-[#8e8e93]" />} placeholder="Артикул или название"
          value={query} onChange={(e) => setQuery(e.target.value)} />
        <Segmented block value={filter} onChange={setFilter}
          options={[{ value: 'generator', label: 'В схемах' }, { value: 'unknown', label: 'Без веса' }, { value: 'all', label: 'Все' }]} />
      </div>

      {groups.length === 0 && <p className="mt-8 text-center text-[#8e8e93]">Ничего не найдено</p>}
      {groups.map((g) => (
        <div key={g.name} className="mb-3">
          <div className="group-title">{g.name}</div>
          <section className="card !p-0">
            {g.items.map((i) => (
              <WeightRow key={i.article} item={i} value={weights[i.article]} onChange={onChange} />
            ))}
          </section>
        </div>
      ))}
    </div>
  )
}
