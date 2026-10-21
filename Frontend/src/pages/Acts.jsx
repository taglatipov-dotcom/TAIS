import { useCallback, useEffect, useMemo, useState } from 'react'
import { App, Button, InputNumber, Modal, Popconfirm, Segmented, Space, Table, Tag, Tooltip } from 'antd'
import { ArrowRightOutlined, DeleteOutlined, EditOutlined, NumberOutlined, PictureOutlined, PlayCircleOutlined, PlusOutlined, RedoOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, constructionText } from '../api.js'

const STATUS = {
  new: { label: 'В работе', color: 'orange' },
  done: { label: 'Готово', color: 'green' },
}

export default function Acts() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const filter = params.get('status') || 'new'
  const [acts, setActs] = useState([])
  const [loading, setLoading] = useState(false)
  const [ispOpen, setIspOpen] = useState(false)
  const [ispStart, setIspStart] = useState(null)
  const [last, setLast] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [list, top] = await Promise.all([api.acts(filter === 'all' ? undefined : filter), api.ispLast()])
      setActs(list)
      setLast(top)
    } catch (e) {
      message.error(e.message)
    } finally {
      setLoading(false)
    }
  }, [filter, message])

  useEffect(() => { load() }, [load])

  const withoutIsp = useMemo(() => acts.filter((a) => a.isp_number == null).length, [acts])

  const openIsp = () => {
    setIspStart(last?.next ?? null)    // по умолчанию — следующий после последнего
    setIspOpen(true)
  }

  const remove = async (id) => {
    try {
      await api.deleteAct(id)
      message.success('Акт удалён')
      load()
    } catch (e) {
      message.error(e.message)
    }
  }

  // Готовый акт — обратно в очередь «В работе», схема будет построена заново
  const redo = async (id) => {
    try {
      await api.reopenAct(id)
      message.success('Акт возвращён в очередь — схема будет построена заново')
      load()
    } catch (e) {
      message.error(e.message)
    }
  }

  const assignIsp = async () => {
    if (!ispStart) return
    try {
      const done = await api.assignIsp(ispStart)
      message.success(`Номера назначены: ${done.length}`)
      setIspOpen(false)
      load()
    } catch (e) {
      message.error(e.message)
    }
  }

  const columns = [
    { title: '№ акта', dataIndex: 'number', width: 110 },
    { title: 'Дата', dataIndex: 'date', width: 110 },
    { title: 'Завод', dataIndex: 'refinery', width: 100 },
    { title: 'Цех / установка', render: (_, a) => [a.department, a.facility, a.location].filter(Boolean).join(' · ') },
    {
      title: 'Конструкции',
      render: (_, a) => a.constructions.map((c, i) => <div key={i}>{constructionText(c)}</div>),
    },
    { title: 'Площадь, м²', width: 110, align: 'right', render: (_, a) => a.area.value.toLocaleString('ru-RU') },
    {
      title: 'Номер ИС',
      width: 260,
      sorter: (a, b) => (a.isp_number ?? -1) - (b.isp_number ?? -1),
      render: (_, a) => (a.isp_full
        ? (
          <div className="leading-tight">
            <div className="font-semibold">ИС{a.isp_number}</div>
            <div className="text-[11px] text-[#8e8e93]">{a.isp_full}</div>
          </div>
        )
        : <Tag color="default">не назначен</Tag>),
    },
    {
      title: 'План', width: 60, align: 'center',
      render: (_, a) => (a.has_picture
        ? <PictureOutlined className="!text-[#34c759]" />
        : <Tooltip title="Нет ситуационного плана"><PictureOutlined className="text-gray-300" /></Tooltip>),
    },
    {
      title: 'Статус', width: 100,
      render: (_, a) => <Tag color={STATUS[a.status]?.color}>{STATUS[a.status]?.label || a.status}</Tag>,
    },
    {
      title: '', width: 130,
      render: (_, a) => (
        <Space>
          {a.status === 'done' && (
            <Popconfirm title="Переделать схему?" description="Акт вернётся в очередь «В работе»"
              okText="Переделать" cancelText="Отмена" onConfirm={() => redo(a.id)}>
              <Tooltip title="Переделать"><Button type="text" icon={<RedoOutlined />} /></Tooltip>
            </Popconfirm>
          )}
          <Tooltip title="Изменить"><Button type="text" icon={<EditOutlined />} onClick={() => navigate(`/acts/${a.id}`)} /></Tooltip>
          <Popconfirm title="Удалить акт?" okText="Удалить" cancelText="Отмена" onConfirm={() => remove(a.id)}>
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="m-0 mr-auto text-[28px] font-bold tracking-tight">Акты</h1>
        <Segmented
          value={filter}
          onChange={(v) => setParams({ status: v })}
          options={[{ value: 'new', label: 'В работе' }, { value: 'done', label: 'Готово' }, { value: 'all', label: 'Все' }]}
        />
        <Button color="default" variant="filled" icon={<NumberOutlined />} onClick={openIsp}>Назначить номера ИС</Button>
        <Button color="default" variant="filled" icon={<PlayCircleOutlined />} onClick={() => navigate('/work')}>Отработать очередь</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/acts/new')}>Добавить акт</Button>
      </div>

      <div className="isp-last">
        <div className="kpi-icon" style={{ color: '#30b0c7', background: '#30b0c71a' }}><NumberOutlined /></div>
        <div className="min-w-0 flex-1">
          <div className="text-[13px] text-[#8e8e93]">Последний назначенный номер ИС</div>
          {last?.isp_number != null ? (
            <div className="flex flex-wrap items-baseline gap-x-3">
              <span className="text-[24px] font-bold tracking-tight">ИС{last.isp_number}</span>
              <span className="truncate text-[13px] text-[#636366]">{last.isp_full} · акт {last.number}</span>
            </div>
          ) : <div className="text-[17px] font-semibold">Номера ещё не назначены</div>}
        </div>
        {last?.isp_number != null && (
          <>
            <Tag color="blue" className="!text-[13px]">Следующий: {last.next}</Tag>
            <Button type="text" icon={<ArrowRightOutlined />} onClick={() => navigate(`/acts/${last.act_id}`)}>Открыть акт</Button>
          </>
        )}
      </div>

      <div className="ios-list">
        <Table rowKey="id" size="middle" loading={loading} columns={columns} dataSource={acts}
          pagination={{ pageSize: 50, hideOnSinglePage: true }}
          onRow={(a) => ({ onDoubleClick: () => navigate(`/acts/${a.id}`) })} />
      </div>

      <Modal title="Назначить номера ИС" open={ispOpen} onOk={assignIsp} onCancel={() => setIspOpen(false)}
        okText="Назначить" cancelText="Отмена" okButtonProps={{ disabled: !ispStart }}>
        <p>
          Актам без номера номера назначаются по порядку добавления, начиная со стартового.
          {filter !== 'all' && ' Учитываются все акты, а не только показанные.'}
        </p>
        {filter === 'all' && <p>Без номера сейчас: {withoutIsp}.</p>}
        <InputNumber min={1} value={ispStart} onChange={setIspStart} placeholder="Стартовый номер" className="w-full" />
      </Modal>
    </div>
  )
}
