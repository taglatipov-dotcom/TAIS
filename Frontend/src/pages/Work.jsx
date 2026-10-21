import { useCallback, useEffect, useState } from 'react'
import { Alert, App, Button, Card, Descriptions, Empty, Image, Progress, Spin } from 'antd'
import { EditOutlined, LeftOutlined, RightOutlined, SendOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { api, constructionText } from '../api.js'
import SchemeView from '../components/SchemeView.jsx'
import { PrintButton } from '../components/SchemeActions.jsx'
import { readBuilt, useBuild } from '../components/BuildRunner.jsx'
import { AutoProgress, AutoRunButton } from '../components/AutoRun.jsx'

// Отработка очереди: акты «в работе» по порядку добавления, по одному или все сразу («Авто»).
// Само построение и окно «Схема готова» — в BuildRunner: они не пропадают при смене экрана.
export default function Work() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const { busy, lastFiles, version, buildAct } = useBuild()
  const lastFile = lastFiles.work
  const [queue, setQueue] = useState([])
  const [built, setBuilt] = useState(readBuilt)
  const [index, setIndex] = useState(0)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadQueue = useCallback(async () => {
    try {
      const pending = await api.acts('new')
      setQueue(pending)
      setIndex((i) => Math.min(i, Math.max(pending.length - 1, 0)))
    } catch (e) {
      message.error(e.message)
    } finally {
      setLoading(false)
    }
  }, [message])

  // перечитываем очередь при входе и после каждого построенного акта (в том числе в авто-режиме)
  useEffect(() => {
    loadQueue()
    setBuilt(readBuilt())
  }, [loadQueue, version])

  const current = queue[index]

  useEffect(() => {
    setPreview(null)
    if (!current) return
    api.actPreview(current.id).then(setPreview).catch((e) => message.error(e.message))
  }, [current, message])

  const building = busy?.kind === 'act' && busy.id === current?.id

  if (loading) return <Spin />
  if (!current) {
    return (
      <div className="flex flex-col gap-4">
        <AutoProgress />
        <div className="rounded-[14px] bg-white py-16 shadow-[0_1px_2px_rgba(0,0,0,0.04),0_2px_12px_rgba(0,0,0,0.04)]">
          <Empty description="Очередь пуста — все акты отработаны">
            <div className="flex justify-center gap-2">
              {lastFile && <PrintButton file={lastFile} />}
              <Button type="primary" onClick={() => navigate('/acts/new')}>Добавить акт</Button>
            </div>
          </Empty>
        </div>
      </div>
    )
  }

  // прогресс этого запуска: отработано / (отработано + осталось в очереди)
  const doneCount = built.filter((id) => !queue.some((a) => a.id === id)).length
  const total = doneCount + queue.length
  const act = preview?.act || current

  return (
    <div className="flex flex-col gap-4">
      <AutoProgress />
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1 rounded-full bg-[rgba(118,118,128,0.12)] p-0.5">
          <Button shape="circle" type="text" icon={<LeftOutlined />} disabled={index === 0} onClick={() => setIndex(index - 1)} />
          <Button shape="circle" type="text" icon={<RightOutlined />} disabled={index >= queue.length - 1} onClick={() => setIndex(index + 1)} />
        </div>
        <div className="flex flex-col">
          <div className="text-[22px] font-bold leading-tight tracking-tight">Акт № {current.number} от {current.date}</div>
          <span className="text-[13px] text-[#8e8e93]">{index + 1} из {queue.length} в очереди</span>
        </div>
        <div className="ml-4 flex w-56 flex-col">
          <span className="text-[12px] text-[#8e8e93]">Отработано: {doneCount} из {total}</span>
          <Progress className="!m-0" percent={total ? Math.round((doneCount / total) * 100) : 0} size="small" showInfo={false} />
        </div>
        <div className="ml-auto flex flex-wrap gap-2">
          <Button color="default" variant="filled" icon={<EditOutlined />} onClick={() => navigate(`/acts/${current.id}`)}>Изменить</Button>
          <Button type="primary" icon={<SendOutlined />} loading={building} onClick={() => buildAct(current.id)}
            disabled={!act.constructions.length || (!!busy && !building)}>
            Построить в nanoCAD
          </Button>
          <AutoRunButton disabled={!!busy} queueSize={queue.length} />
          <PrintButton file={busy ? null : lastFile} />
        </div>
      </div>

      {act.isp_number == null && (
        <Alert type="warning" showIcon message="У акта нет номера ИС"
          description="Назначьте номера в списке актов («Назначить номера ИС») или впишите номер в акте." />
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
        <Card size="small">
          <Descriptions size="small" column={1} bordered title="Основная надпись">
            <Descriptions.Item label="Номер ИС">{act.isp_full || '—'}</Descriptions.Item>
            <Descriptions.Item label="Акт">№{act.number} от {act.date}</Descriptions.Item>
            <Descriptions.Item label="Завод">{act.refinery_full}</Descriptions.Item>
            <Descriptions.Item label="Место">{act.location_full}</Descriptions.Item>
            <Descriptions.Item label="Конструкции">
              {act.constructions.map((c, i) => <div key={i}>{constructionText(c)}</div>)}
            </Descriptions.Item>
            <Descriptions.Item label="Площадь, м²">{act.area?.text}</Descriptions.Item>
          </Descriptions>
        </Card>
        <Card size="small" title="Ситуационный план">
          {act.has_picture
            ? <Image src={api.pictureUrl(act.id, act.id)} alt="Ситуационный план" className="rounded-lg" />
            : <Alert type="info" message="Нет картинки — схема построится без неё" />}
        </Card>
      </div>

      <Card>{preview ? <SchemeView scheme={preview.scheme} /> : <Spin />}</Card>
    </div>
  )
}
