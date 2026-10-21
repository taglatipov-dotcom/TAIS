import { Button, Form, InputNumber, Select, Switch } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'

// Типы конструкций и грани — как в настольном TAIS (русские подписи, английские коды)
export const KIND_OPTIONS = [
  { value: 'auto', label: 'Автоматически' },
  { value: 'tower', label: 'Башенные' },
  { value: 'facade', label: 'Фасадные' },
  { value: 'widening', label: 'Уширение' },
  { value: 'balcony', label: 'Балкон (консольно-опорные)' },
  { value: 'radial', label: 'Радиальные' },
]
export const ATTACHABLE = ['widening', 'balcony']
export const SIDE_OPTIONS = [
  { value: 'y0', label: 'Передняя сторона' },
  { value: 'y1', label: 'Задняя сторона' },
  { value: 'x0', label: 'Левый торец' },
  { value: 'x1', label: 'Правый торец' },
]

export const NEW_CONSTRUCTION = {
  kind: 'auto', length: 3, width: 1, height: 6.2, intermediate_decks: true, entrance: true, pads: false,
  attach_to: 0, side: 'y0', offset: 0, widening: false, widening_width: 1, widening_height: null,
}

// Числа: запятая и точка — обе годятся
const parser = (v) => (v ?? '').replace(/\s/g, '').replace(',', '.')

// Показ без лишних нулей: 3, а не 3.00 (пока человек печатает — как набрано)
const formatter = (v, info) => {
  if (info?.userTyping) return info.input
  const s = v === undefined || v === null ? '' : String(v)
  return s.includes('.') ? s.replace(/\.?0+$/, '') : s
}

function Num(props) {
  return <InputNumber className="!w-full" inputMode="decimal" parser={parser} formatter={formatter} {...props} />
}

// Переключатель строкой «подпись — тумблер», как в настройках телефона
function Toggle({ name, label }) {
  return (
    <div className="toggle-row">
      <span>{label}</span>
      <Form.Item name={name} valuePropName="checked" noStyle>
        <Switch />
      </Form.Item>
    </div>
  )
}

function ConstructionCard({ field, index, count, remove }) {
  const form = Form.useFormInstance()
  const all = Form.useWatch('constructions', form) || []
  const row = all[field.name] || {}
  const balcony = row.kind === 'balcony'
  const widening = ATTACHABLE.includes(row.kind)
  const attached = widening && row.attach_to > 0
  const radial = row.kind === 'radial'
  const alongX = row.side === 'y0' || row.side === 'y1'
  const attachOptions = [
    { value: 0, label: 'Отдельно (к стоящим лесам)' },
    ...all
      .map((c, i) => ({ c, i }))
      .filter(({ c, i }) => i !== field.name && !ATTACHABLE.includes(c?.kind) && c?.kind !== 'radial')
      .map(({ c, i }) => ({ value: i + 1, label: `№${i + 1} ${c?.length ?? ''}×${c?.width ?? ''}×${c?.height ?? ''}` })),
  ]
  const f = (key) => [field.name, key]

  return (
    <section className="card">
      <div className="mb-3 flex items-center gap-2">
        <span className="badge">{index + 1}</span>
        <Form.Item name={f('kind')} noStyle>
          <Select options={KIND_OPTIONS} className="min-w-0 flex-1" />
        </Form.Item>
        <Button type="text" danger icon={<DeleteOutlined />} disabled={count === 1}
          onClick={() => remove(field.name)} aria-label="Убрать конструкцию" />
      </div>
      <div className="grid grid-cols-2 gap-x-3">
        <Form.Item name={f('length')} label={widening ? 'Вдоль грани, м' : radial ? 'Длина кольца, м' : 'Длина, м'}
          rules={[{ required: true, message: 'Нужна длина' }]}>
          <Num min={0.75} max={200} step={0.25} />
        </Form.Item>
        <Form.Item name={f('width')} label={widening ? 'Вынос, м' : 'Ширина, м'}
          rules={[{ required: true, message: 'Нужна ширина' }]}>
          <Num min={0.75} max={10} step={0.25} />
        </Form.Item>
        <Form.Item name={f('height')} label={balcony ? 'Высота стоящих лесов, м' : 'Высота, м'}
          hidden={balcony && attached}
          rules={[{ required: !(balcony && attached), message: 'Нужна высота' }]}>
          <Num min={1.5} max={60} step={0.1} />
        </Form.Item>
        {radial && row.widening && (
          <>
            <Form.Item name={f('widening_width')} label="Вынос уширения, м"
              rules={[{ required: true, message: 'Нужен вынос' }]}>
              <Num min={0.75} max={10} step={0.25} />
            </Form.Item>
            <Form.Item name={f('widening_height')} label="Высота уширения, м" extra="Пусто — как у лесов">
              <Num min={1.5} max={60} step={0.5} placeholder="как у лесов" />
            </Form.Item>
          </>
        )}
      </div>
      {radial && <p className="hint">Длина кольца — сумма длин всех ячеек по внутренней стороне.</p>}
      {widening && (
        <>
          <Form.Item name={f('attach_to')} label="Пристроено к">
            <Select options={attachOptions} />
          </Form.Item>
          {attached && (
            <div className="grid grid-cols-2 gap-x-3">
              <Form.Item name={f('side')} label="Грань">
                <Select options={SIDE_OPTIONS} />
              </Form.Item>
              <Form.Item name={f('offset')} label="Отступ, м"
                extra={alongX ? 'от левого торца' : 'от передней стороны'}>
                <Num min={0} max={200} step={0.25} />
              </Form.Item>
            </div>
          )}
        </>
      )}
      <div className="toggles">
        {!widening && <Toggle name={f('intermediate_decks')} label="Настилы через 2 м" />}
        {!widening && <Toggle name={f('entrance')} label="Входная группа" />}
        {radial && <Toggle name={f('widening')} label="Уширения наружу" />}
        {!balcony && <Toggle name={f('pads')} label="Подкладки под домкраты" />}
      </div>
    </section>
  )
}

// Список конструкций одной схемы (Form.List по полю constructions)
export default function ConstructionForm() {
  return (
    <Form.List name="constructions">
      {(fields, { add, remove }) => (
        <div className="flex flex-col gap-3">
          {fields.map((field, index) => (
            <ConstructionCard key={field.key} field={field} index={index} count={fields.length} remove={remove} />
          ))}
          <Button type="dashed" size="large" icon={<PlusOutlined />} onClick={() => add({ ...NEW_CONSTRUCTION })}>
            Добавить конструкцию
          </Button>
        </div>
      )}
    </Form.List>
  )
}
