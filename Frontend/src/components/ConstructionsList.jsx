import { Button, Form, InputNumber, Select, Switch, Tooltip } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { ATTACHABLE, KIND_OPTIONS, SIDE_OPTIONS } from '../api.js'

export const NEW_CONSTRUCTION = {
  kind: 'auto', length: 3, width: 1, height: 6.2, intermediate_decks: true, entrance: true, pads: false,
  attach_to: 0, side: 'y0', offset: 0, widening: false, widening_width: 1, widening_height: null,
}

// Одна строка списка: у уширения и балкона свои поля (к какой конструкции, грань, отступ).
// У балкона нет своей высоты: пристроенный — по верху основной, отдельный — по высоте стоящих лесов.
function ConstructionRow({ name, field, index, count, remove }) {
  const form = Form.useFormInstance()
  const all = Form.useWatch(name, form) || []
  const row = all[field.name] || {}
  const balcony = row.kind === 'balcony'
  const widening = ATTACHABLE.includes(row.kind)
  const attached = widening && row.attach_to > 0
  const radial = row.kind === 'radial'
  const attachOptions = [
    { value: 0, label: 'Отдельно (к стоящей)' },
    ...all
      .map((c, i) => ({ c, i }))
      .filter(({ c, i }) => i !== field.name && !ATTACHABLE.includes(c?.kind) && c?.kind !== 'radial')
      .map(({ c, i }) => ({ value: i + 1, label: `№${i + 1} ${c?.length ?? ''}×${c?.width ?? ''}×${c?.height ?? ''}` })),
  ]
  const alongX = row.side === 'y0' || row.side === 'y1'

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-xl bg-[#f7f7fa] p-3">
      <div className="mb-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-white text-xs font-semibold text-[#8e8e93]">{index + 1}</div>
      <Form.Item name={[field.name, 'kind']} label="Тип" className="!mb-0">
        <Select options={KIND_OPTIONS} style={{ width: 160 }} />
      </Form.Item>
      <Form.Item name={[field.name, 'length']}
        label={widening ? 'Длина вдоль грани, м' : radial ? (
          <Tooltip title="Сумма длин всех ячеек кольца (по внутренней стороне)">
            <span className="cursor-help border-b border-dashed border-gray-400">Длина кольца, м</span>
          </Tooltip>
        ) : 'Длина, м'}
        rules={[{ required: true, message: 'Нужна длина' }]} className="!mb-0">
        <InputNumber min={0.75} max={200} step={0.25} decimalSeparator="," />
      </Form.Item>
      <Form.Item name={[field.name, 'width']} label={widening ? 'Вынос, м' : 'Ширина, м'}
        rules={[{ required: true, message: 'Нужна ширина' }]} className="!mb-0">
        <InputNumber min={0.75} max={10} step={0.25} decimalSeparator="," />
      </Form.Item>
      {/* у пристроенного балкона высоты нет: поле скрыто, но остаётся в форме
          (validateFields возвращает только зарегистрированные поля) */}
      <Form.Item name={[field.name, 'height']} label={balcony ? 'Высота стоящих лесов, м' : 'Высота, м'}
        hidden={balcony && attached}
        rules={[{ required: !(balcony && attached), message: 'Нужна высота' }]} className="!mb-0">
        <InputNumber min={1.5} max={60} step={0.1} decimalSeparator="," />
      </Form.Item>
      {widening ? (
        <>
          <Form.Item name={[field.name, 'attach_to']} label="Пристроено к" className="!mb-0">
            <Select options={attachOptions} style={{ width: 190 }} />
          </Form.Item>
          {attached && (
            <>
              <Form.Item name={[field.name, 'side']} label="Грань" className="!mb-0">
                <Select options={SIDE_OPTIONS} style={{ width: 170 }} />
              </Form.Item>
              <Form.Item name={[field.name, 'offset']} className="!mb-0" label={
                <Tooltip title={alongX ? 'От левого торца основной конструкции' : 'От передней стороны основной конструкции'}>
                  <span className="cursor-help border-b border-dashed border-gray-400">Отступ, м</span>
                </Tooltip>
              }>
                <InputNumber min={0} max={200} step={0.25} decimalSeparator="," />
              </Form.Item>
            </>
          )}
        </>
      ) : (
        <>
          <Form.Item name={[field.name, 'intermediate_decks']} label="Настилы через 2 м" valuePropName="checked" className="!mb-0">
            <Switch size="small" />
          </Form.Item>
          <Form.Item name={[field.name, 'entrance']} label="Входная группа" valuePropName="checked" className="!mb-0">
            <Switch size="small" />
          </Form.Item>
          {radial && (
            <Form.Item name={[field.name, 'widening']} label="Уширения наружу" valuePropName="checked" className="!mb-0">
              <Switch size="small" />
            </Form.Item>
          )}
          {radial && row.widening && (
            <>
              <Form.Item name={[field.name, 'widening_width']} label="Вынос уширения, м"
                rules={[{ required: true, message: 'Нужен вынос' }]} className="!mb-0">
                <InputNumber min={0.75} max={10} step={0.25} decimalSeparator="," />
              </Form.Item>
              <Form.Item name={[field.name, 'widening_height']} className="!mb-0" label={
                <Tooltip title="Пусто — на всю высоту лесов">
                  <span className="cursor-help border-b border-dashed border-gray-400">Высота уширения, м</span>
                </Tooltip>
              }>
                <InputNumber min={1.5} max={60} step={0.5} decimalSeparator="," placeholder="как у лесов" />
              </Form.Item>
            </>
          )}
        </>
      )}
      {!balcony && (
        <Form.Item name={[field.name, 'pads']} label="Подкладки" valuePropName="checked" className="!mb-0">
          <Switch size="small" />
        </Form.Item>
      )}
      <Tooltip title="Убрать конструкцию">
        <Button danger type="text" icon={<DeleteOutlined />} disabled={count === 1}
          onClick={() => remove(field.name)} />
      </Tooltip>
    </div>
  )
}

// Список конструкций одной схемы (Form.List по полю "constructions")
export default function ConstructionsList({ name = 'constructions' }) {
  return (
    <Form.List name={name}>
      {(fields, { add, remove }) => (
        <div className="flex flex-col gap-2">
          {fields.map((field, index) => (
            <ConstructionRow key={field.key} name={name} field={field} index={index}
              count={fields.length} remove={remove} />
          ))}
          <Button type="dashed" icon={<PlusOutlined />} onClick={() => add({ ...NEW_CONSTRUCTION })}>
            Добавить конструкцию
          </Button>
        </div>
      )}
    </Form.List>
  )
}
