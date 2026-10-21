import { Alert, Descriptions, Table, Tabs } from 'antd'
import Preview from './Preview.jsx'

const m = (mm) => (mm / 1000).toLocaleString('ru-RU')
// 24 ячейки: 8 × 3 м → «8 × 3 м»; смешанные — по группам
const cellsText = (bays) => {
  const groups = {}
  bays.forEach((b) => { groups[b] = (groups[b] || 0) + 1 })
  return Object.entries(groups).sort((a, b) => b[0] - a[0]).map(([b, n]) => `${n} × ${m(+b)} м`).join(' + ')
}
const num = (v) => (v == null ? '—' : v.toLocaleString('ru-RU'))

const specColumns = [
  { title: 'Артикул', dataIndex: 'article', width: 130 },
  { title: 'Наименование', dataIndex: 'name' },
  { title: 'Кол-во', dataIndex: 'qty', width: 90, align: 'right' },
  { title: 'Вес 1 шт, кг', dataIndex: 'unit_weight', width: 120, align: 'right', render: num },
  { title: 'Вес, кг', dataIndex: 'total_weight', width: 110, align: 'right', render: num },
]

// Результат расчёта схемы: конструкции, виды, спецификация
export default function SchemeView({ scheme }) {
  if (!scheme) return null
  return (
    <div className="flex flex-col gap-3">
      {scheme.warnings.length > 0 && (
        <Alert type="warning" showIcon message="Обратите внимание" description={
          <ul className="m-0 pl-4">{scheme.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        } />
      )}
      {scheme.parts.map((p) => (
        <Descriptions key={p.n} size="small" bordered column={{ xs: 1, md: 3 }}
          title={`${scheme.parts.length > 1 ? `${p.n}. ` : ''}${p.kind_label} ${p.length}×${p.width}` +
            (p.kind === 'balcony' ? ` м, к лесам высотой ${p.height} м` : `×${p.height} м`) +
            (p.kind === 'radial' ? ` (габарит ${m(p.grid.xs[1])}×${m(p.grid.ys[1])} м)` : '')}>
          {p.grid.radial ? (
            <>
              <Descriptions.Item label="Ячейки кольца">{cellsText(p.grid.bays_x)}</Descriptions.Item>
              <Descriptions.Item label="Внутренний радиус">{m(p.grid.radial.radius)} м</Descriptions.Item>
              <Descriptions.Item label="Поворот">
                {p.grid.radial.turn.map((t) => `${t.toLocaleString('ru-RU')}°`).join(', ')}
                {p.grid.radial.per_section > 1 ? ` через ${p.grid.radial.per_section} ячейки` : ' в каждом стыке'}
              </Descriptions.Item>
              <Descriptions.Item label="Вставки снаружи">
                {p.grid.radial.inserts.map(([l, d]) => `ригель ${m(l)} м (в ${m(d)} м от внутр. стороны)`).join('; ')}
              </Descriptions.Item>
            </>
          ) : (
            <Descriptions.Item label="Пролёты по длине">{p.grid.bays_x.map(m).join(' + ')} м</Descriptions.Item>
          )}
          <Descriptions.Item label="Пролёты по ширине">{p.grid.bays_y.map(m).join(' + ')} м</Descriptions.Item>
          <Descriptions.Item label="Настилы">{p.grid.decks.length ? `${p.grid.decks.map(m).join('; ')} м` : 'нет'}</Descriptions.Item>
          {p.grid.widening_levels?.length > 0 && (
            <Descriptions.Item label="Ригели уширения">{p.grid.widening_levels.map(m).join('; ')} м</Descriptions.Item>
          )}
          {p.widenings?.map((w) => (
            <Descriptions.Item key={w.n} label={`${w.kind_label} №${w.n}`}>
              {w.length}×{w.width}{w.kind === 'balcony' ? '' : `×${w.height}`} м, {w.side_label}, отступ {w.offset} м
            </Descriptions.Item>
          ))}
          <Descriptions.Item label="Верх стоек">{m(p.grid.top)} м</Descriptions.Item>
          <Descriptions.Item label="Сдвиг (кроме домкратов)">
            {p.grid.lift === 0 ? 'нет' : `${p.grid.lift > 0 ? '+' : '−'}${m(Math.abs(p.grid.lift))} м`}
          </Descriptions.Item>
        </Descriptions>
      ))}
      <Tabs
        items={[
          { key: 'preview', label: 'Виды', children: <Preview elements={scheme.elements} /> },
          {
            key: 'spec',
            label: `Спецификация (${scheme.spec.rows.length})`,
            children: (
              <Table size="small" rowKey="article" columns={specColumns} dataSource={scheme.spec.rows} pagination={false}
                summary={() => (
                  <Table.Summary.Row>
                    <Table.Summary.Cell index={0} colSpan={4} className="text-right">
                      Итого, кг{scheme.spec.unknown_weights ? ` (без ${scheme.spec.unknown_weights} поз. с неизвестным весом)` : ''}
                    </Table.Summary.Cell>
                    <Table.Summary.Cell index={1} align="right">{num(scheme.spec.total_weight)}</Table.Summary.Cell>
                  </Table.Summary.Row>
                )} />
            ),
          },
        ]}
      />
    </div>
  )
}
