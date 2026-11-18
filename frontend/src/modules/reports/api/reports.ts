import { queryOptions } from '@tanstack/react-query'

import { apiGet } from '@/common/api-client'

export type ChannelFilter = 'all' | 'telegram'

export interface ReportFilters {
  from: string
  to: string
  managerId: string
  channel: ChannelFilter
}

export interface ReportPeriod {
  from: string
  to: string
  timezone: string
}

export interface ReportKpi {
  conversations: number
  answered: number
  closed: number
  closed_percent: number
  average_response_seconds: number | null
}

export interface ReportManagerRow extends ReportKpi {
  id: number | null
  name: string
}

export interface Report {
  period: ReportPeriod
  filters: {
    manager_id: number | null
    manager_name: string | null
    channel: ChannelFilter
  }
  empty: boolean
  kpi: ReportKpi
  managers: ReportManagerRow[]
}

export type ReportResult =
  | { kind: 'success'; report: Report }
  | { kind: 'unauthorized' }
  | { kind: 'invalid-period' }
  | { kind: 'failed'; status: number }

export async function getReport(
  filters: ReportFilters,
  signal?: AbortSignal,
): Promise<ReportResult> {
  const params = new URLSearchParams()
  if (filters.from) {
    params.set('from', filters.from)
  }
  if (filters.to) {
    params.set('to', filters.to)
  }
  if (filters.managerId) {
    params.set('manager_id', filters.managerId)
  }
  params.set('channel', filters.channel)

  const response = await apiGet<Report>(`/admin/reports/statistics?${params.toString()}`, signal)
  if (response.status === 200 && response.data && 'kpi' in response.data) {
    return { kind: 'success', report: response.data }
  }
  if (response.status === 401) {
    return { kind: 'unauthorized' }
  }
  if (response.status === 422) {
    return { kind: 'invalid-period' }
  }
  return { kind: 'failed', status: response.status }
}

export const reportQueryOptions = (filters: ReportFilters) =>
  queryOptions({
    queryKey: ['reports', filters.from, filters.to, filters.managerId, filters.channel],
    queryFn: ({ signal }) => getReport(filters, signal),
    placeholderData: (previous) => previous,
    retry: false,
  })
