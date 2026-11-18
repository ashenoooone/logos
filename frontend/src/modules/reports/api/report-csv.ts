import type { Report } from './reports'

const MONTHS = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
] as const

/** Среднее время ответа: 252 → «4 мин 12 с», пусто → «—». */
export function formatDuration(seconds: number | null): string {
  if (seconds === null) {
    return '—'
  }
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  if (minutes === 0) {
    return `${rest} с`
  }
  return rest === 0 ? `${minutes} мин` : `${minutes} мин ${rest} с`
}

export function formatNumber(value: number): string {
  return value.toLocaleString('ru-RU')
}

function parts(iso: string): { day: number; month: number; year: number } {
  const [year, month, day] = iso.split('-').map(Number)
  return { day, month: month - 1, year }
}

/** «1–19 ноября» или «28 ноября – 3 декабря»; год добавляется при смене года. */
export function formatPeriod(from: string, to: string): string {
  const start = parts(from)
  const end = parts(to)
  const startLabel = `${start.day} ${MONTHS[start.month]}`
  const endLabel = `${end.day} ${MONTHS[end.month]}`
  if (start.month === end.month && start.year === end.year) {
    return start.day === end.day
      ? `${startLabel} ${start.year}`
      : `${start.day}–${end.day} ${MONTHS[start.month]} ${start.year}`
  }
  return `${startLabel} ${start.year} – ${endLabel} ${end.year}`
}

function csvCell(value: string | number): string {
  const text = String(value)
  return /[;"\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

/** Та же таблица и фильтры, что на экране; UTF-8 с BOM и «;» для Excel. */
export function buildReportCsv(report: Report): string {
  const rows: (string | number)[][] = [
    ['Период', `${report.period.from} – ${report.period.to}`],
    ['Менеджер', report.filters.manager_name ?? 'Все'],
    ['Канал', report.filters.channel === 'telegram' ? 'Telegram' : 'Все каналы'],
    ['Часовой пояс', report.period.timezone],
    [],
    ['Менеджер', 'Обращений', 'Среднее время ответа', 'Закрыто', 'Доля закрытых'],
    ...report.managers.map((manager) => [
      manager.name,
      manager.conversations,
      formatDuration(manager.average_response_seconds),
      manager.closed,
      `${manager.closed_percent}%`,
    ]),
    [
      'Итого',
      report.kpi.conversations,
      formatDuration(report.kpi.average_response_seconds),
      report.kpi.closed,
      `${report.kpi.closed_percent}%`,
    ],
  ]
  const body = rows.map((row) => row.map(csvCell).join(';')).join('\r\n')
  return `\ufeff${body}\r\n`
}

export function reportFileName(report: Report): string {
  return `report_${report.period.from}_${report.period.to}.csv`
}
