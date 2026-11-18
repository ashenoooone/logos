import { describe, expect, it } from 'vitest'

import { buildReportCsv, formatDuration, formatPeriod } from './report-csv'
import type { Report } from './reports'

const report: Report = {
  period: { from: '2026-11-01', to: '2026-11-19', timezone: 'Europe/Moscow' },
  filters: { manager_id: 1, manager_name: 'Анна Петрова', channel: 'telegram' },
  empty: false,
  kpi: {
    conversations: 2,
    answered: 2,
    closed: 1,
    closed_percent: 50,
    average_response_seconds: 252,
  },
  managers: [
    {
      id: 1,
      name: 'Анна Петрова',
      conversations: 2,
      answered: 2,
      closed: 1,
      closed_percent: 50,
      average_response_seconds: 252,
    },
  ],
}

describe('buildReportCsv', () => {
  it('пишет BOM, разделитель «;» и фильтры в шапке', () => {
    const csv = buildReportCsv(report)
    expect(csv.startsWith('\ufeff')).toBe(true)
    const lines = csv.slice(1).trimEnd().split('\r\n')
    expect(lines[0]).toBe('Период;2026-11-01 – 2026-11-19')
    expect(lines[1]).toBe('Менеджер;Анна Петрова')
    expect(lines[2]).toBe('Канал;Telegram')
    expect(lines[5]).toBe('Менеджер;Обращений;Среднее время ответа;Закрыто;Доля закрытых')
    expect(lines[6]).toBe('Анна Петрова;2;4 мин 12 с;1;50%')
    expect(lines[7]).toBe('Итого;2;4 мин 12 с;1;50%')
  })
})

describe('formatPeriod', () => {
  it('сокращает один месяц и сохраняет год', () => {
    expect(formatPeriod('2026-11-01', '2026-11-19')).toBe('1–19 ноября 2026')
    expect(formatPeriod('2026-11-28', '2026-12-03')).toBe(
      '28 ноября 2026 – 3 декабря 2026',
    )
  })
})

describe('formatDuration', () => {
  it('показывает минуты и секунды, пустое значение — прочерк', () => {
    expect(formatDuration(252)).toBe('4 мин 12 с')
    expect(formatDuration(240)).toBe('4 мин')
    expect(formatDuration(45)).toBe('45 с')
    expect(formatDuration(null)).toBe('—')
  })
})
