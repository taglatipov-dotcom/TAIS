import { useMemo, useState } from 'react'
import { Alert, Button, Empty, Segmented } from 'antd'
import { LeftOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import Views from '../components/Views.jsx'
import { spec } from '../generator/index.js'
import { useStore } from '../App.jsx'

const m = (mm) => (mm / 1000).toLocaleString('ru-RU')
const num = (v) => (v == null ? '—' : v.toLocaleString('ru-RU'))
const cellsText = (bays) => {
  const groups = {}
  bays.forEach((b) => { groups[b] = (groups[b] || 0) + 1 })
  return Object.entries(groups).sort((a, b) => b[0] - a[0]).map(([b, n]) => `${n} × ${m(+b)} м`).join(' + ')
}

function Row({ label, children }) {
  return (
    <div className="kv">
      <span className="text-[#8e8e93]">{label}</span>
      <span className="text-right">{children}</span>
    </div>
  )
}

function partTitle(p, many) {
  return `${many ? `${p.n}. ` : ''}${p.kind_label} ${p.length}×${p.width}` +
    (p.kind === 'balcony' ? ` м, к лесам ${p.height} м` : `×${p.height} м`)
}

function Summary({ scheme }) {
  return (
    <div className="flex flex-col gap-3">
      {scheme.parts.map((p) => (
        <section key={p.n} className="card">
          <h3 className="mb-2 text-[15px] font-semibold">{partTitle(p, scheme.parts.length > 1)}</h3>
          {p.grid.radial ? (
            <>
              <Row label="Габарит">{m(p.grid.xs[1])}×{m(p.grid.ys[1])} м</Row>
              <Row label="Ячейки кольца">{cellsText(p.grid.bays_x)}</Row>
              <Row label="Внутренний радиус">{m(p.grid.radial.radius)} м</Row>
              <Row label="Поворот">
                {p.grid.radial.turn.map((t) => `${t.toLocaleString('ru-RU')}°`).join(', ')}
                {p.grid.radial.per_section > 1 ? ` через ${p.grid.radial.per_section} ячейки` : ' в каждом стыке'}
              </Row>
              <Row label="Вставки снаружи">
                {p.grid.radial.inserts.map(([l, d]) => `ригель ${m(l)} м (в ${m(d)} м)`).join('; ')}
              </Row>
            </>
          ) : (
            <Row label="Пролёты по длине">{p.grid.bays_x.map(m).join(' + ')} м</Row>
          )}
          <Row label="Пролёты по ширине">{p.grid.bays_y.map(m).join(' + ')} м</Row>
          <Row label="Настилы">{p.grid.decks.length ? `${p.grid.decks.map(m).join('; ')} м` : 'нет'}</Row>
          {p.grid.widening_levels?.length > 0 && (
            <Row label="Ригели уширения">{p.grid.widening_levels.map(m).join('; ')} м</Row>
          )}
          {p.widenings?.map((w) => (
            <Row key={w.n} label={`${w.kind_label} №${w.n}`}>
              {w.length}×{w.width}{w.kind === 'balcony' ? '' : `×${w.height}`} м, {w.side_label}, отступ {w.offset} м
            </Row>
          ))}
          <Row label="Верх стоек">{m(p.grid.top)} м</Row>
          <Row label="Сдвиг (кроме домкратов)">
            {p.grid.lift === 0 ? 'нет' : `${p.grid.lift > 0 ? '+' : '−'}${m(Math.abs(p.grid.lift))} м`}
          </Row>
        </section>
      ))}
    </div>
  )
}

function SpecList({ table, onSettings }) {
  const qty = table.rows.reduce((s, r) => s + r.qty, 0)
  return (
    <div className="flex flex-col gap-3">
      <section className="card total">
        <div>
          <div className="text-[13px] text-[#8e8e93]">Общий вес</div>
          <div className="text-[28px] font-bold tracking-tight">{num(table.total_weight)} кг</div>
        </div>
        <div className="text-right text-[13px] text-[#8e8e93]">
          <div>{table.rows.length} поз.</div>
          <div>{qty.toLocaleString('ru-RU')} шт.</div>
        </div>
      </section>
      {table.unknown_weights > 0 && (
        <Alert type="warning" showIcon
          title={`Без веса: ${table.unknown_weights} поз. — в общий вес не вошли`}
          action={<Button size="small" type="link" onClick={onSettings}>Указать</Button>} />
      )}
      <section className="card !p-0">
        {table.rows.map((r) => (
          <div key={r.article} className="spec-row">
            <div className="min-w-0 flex-1">
              <div className="font-medium leading-snug">{r.name}</div>
              <div className="text-[12px] text-[#8e8e93]">
                {r.article} · {r.unit_weight == null ? <span className="text-[#ff9500]">вес не указан</span> : `${num(r.unit_weight)} кг/шт`}
              </div>
            </div>
            <div className="text-right">
              <div className="text-[17px] font-semibold">{r.qty} шт</div>
              <div className="text-[12px] text-[#8e8e93]">{num(r.total_weight)} кг</div>
            </div>
          </div>
        ))}
      </section>
    </div>
  )
}

export default function Result() {
  const navigate = useNavigate()
  const { result, weights } = useStore()
  const [tab, setTab] = useState('spec')
  // спецификация пересчитывается при смене весов в настройках
  const table = useMemo(
    () => (result ? spec.build(result.scheme.elements.map((e) => e.article)) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [result, weights],
  )

  if (!result) {
    return (
      <div className="page">
        <Empty className="mt-16" description="Сначала выполните расчёт">
          <Button type="primary" onClick={() => navigate('/')}>К расчёту</Button>
        </Empty>
      </div>
    )
  }
  const { scheme } = result
  return (
    <div className="page">
      <header className="page-header !mb-3">
        <Button type="text" icon={<LeftOutlined />} onClick={() => navigate('/')} className="!px-1">Изменить</Button>
        <h1 className="page-title ml-auto !text-[20px]">Результат</h1>
      </header>
      {scheme.warnings.length > 0 && (
        <Alert className="!mb-3" type="warning" showIcon title="Обратите внимание" description={
          <ul className="m-0 pl-4">{scheme.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        } />
      )}
      <Segmented block className="seg-fit !mb-3" value={tab} onChange={setTab}
        options={[{ value: 'spec', label: 'Спецификация' }, { value: 'views', label: 'Виды' }, { value: 'data', label: 'Данные' }]} />
      {tab === 'spec' && <SpecList table={table} onSettings={() => navigate('/settings?unknown=1')} />}
      {tab === 'views' && <Views elements={scheme.elements} />}
      {tab === 'data' && <Summary scheme={scheme} />}
    </div>
  )
}
