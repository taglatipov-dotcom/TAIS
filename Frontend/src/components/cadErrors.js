import { api, desktop } from '../api.js'

// Общая обработка ошибок построения в nanoCAD (страницы «Отработка» и «Генератор»)
export function showCadError(e, { modal, message }) {
  if (e.code === 'gen_py_cache') {
    modal.confirm({
      title: 'Ошибка кэша gen_py',
      content: e.message,
      okText: desktop ? 'Очистить и перезапустить' : 'Очистить кэш',
      cancelText: 'Отмена',
      onOk: async () => {
        try {
          const res = await api.clearGenPy()
          if (res.failed?.length) {
            modal.error({
              title: 'Не удалось удалить папку',
              content: `${res.failed.join('; ')}. Закройте TAIS и nanoCAD и удалите папку вручную.`,
            })
            return
          }
          if (desktop?.relaunch) {
            await desktop.relaunch()
          } else {
            message.success('Кэш удалён. Перезапустите TAIS и nanoCAD.')
          }
        } catch (err) {
          message.error(err.message)
        }
      },
    })
    return
  }
  if (['nanocad_not_installed', 'nanocad_unsupported_os', 'template_missing', 'no_isp', 'file_missing',
    'print_no_layouts'].includes(e.code)) {
    modal.warning({ title: 'Не получилось построить', content: e.message })
    return
  }
  message.error(e.message)
}

// Блоки, которых нет в шаблоне (в спецификации они учтены)
export function missingText(file) {
  return file?.missing?.length ? ` Нет в шаблоне (учтены только в спецификации): ${file.missing.join(', ')}.` : ''
}

// Итог заполнения таблицы спецификации шаблона
export function specText(file) {
  const s = file?.spec
  if (!s) return ''
  if (s.ok) return ` Спецификация: ${s.rows} строк.${s.notes?.length ? ` (${s.notes.join('; ')})` : ''}`
  return ` Спецификация НЕ заполнена: ${s.reason}. Подробности — в %APPDATA%\\TAIS\\logs\\backend.log.`
}
