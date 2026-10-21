import { useRef } from 'react'
import { App, Image } from 'antd'
import { PictureOutlined } from '@ant-design/icons'

// Ситуационный план: вставка картинки из буфера обмена (Ctrl+V) или выбор файла
export default function PicturePaste({ src, onPicture, error }) {
  const { message } = App.useApp()
  const input = useRef(null)

  const readFile = (file) => {
    if (!file || !file.type.startsWith('image/')) {
      message.warning('В буфере обмена нет картинки')
      return
    }
    const reader = new FileReader()
    reader.onload = () => onPicture(reader.result)
    reader.readAsDataURL(file)
  }

  const onPaste = (e) => {
    const item = [...e.clipboardData.items].find((i) => i.type.startsWith('image/'))
    e.preventDefault()
    readFile(item?.getAsFile())
  }

  const border = error ? 'border-[#ff3b30] bg-[#fff5f4]' : 'border-[#d1d1d6] bg-[#f7f7fa] focus:border-[#007aff]'
  return (
    <div className="flex flex-col gap-1">
      <div
        tabIndex={0}
        onPaste={onPaste}
        className={`flex min-h-44 flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-3 text-center text-[#8e8e93] outline-none transition-colors ${border}`}
      >
        {src ? (
          <Image src={src} alt="Ситуационный план" preview={false} className="max-h-60 rounded-lg" />
        ) : (
          <>
            <PictureOutlined className="text-3xl text-[#c7c7cc]" />
            <span>Нажмите сюда и вставьте картинку (Ctrl+V)</span>
          </>
        )}
        {src && <span className="text-xs">Ctrl+V — заменить картинку</span>}
        <button type="button" className="text-sm font-medium text-[#007aff]" onClick={() => input.current?.click()}>
          или выбрать файл
        </button>
        <input ref={input} type="file" accept="image/*" style={{ display: 'none' }}
          onChange={(e) => readFile(e.target.files?.[0])} />
      </div>
      {error && <div className="text-[13px] text-[#ff3b30]">Без ситуационного плана акт не сохранить</div>}
    </div>
  )
}
