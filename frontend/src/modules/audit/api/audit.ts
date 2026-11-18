import { queryOptions } from '@tanstack/react-query'

import { apiDownload, apiGet } from '@/common/api-client'

export type AuditAction = 'login' | 'logout' | 'tag_deleted' | 'export'

export const AUDIT_ACTION_LABELS: Record<AuditAction, string> = {
  login: 'Вход',
  logout: 'Выход',
  tag_deleted: 'Удаление',
  export: 'Экспорт',
}

export interface AuditActor {
  kind: 'administrator' | 'manager'
  id: number
  name: string
}

export interface AuditEvent {
  id: number
  occurred_at: string
  actor: AuditActor
  action: AuditAction
  description: string
  ip: string
}

export interface AuditFilters {
  actor: string | null
  action: AuditAction | null
  from: string | null
  to: string | null
}

export interface AuditPage {
  events: AuditEvent[]
  actors: AuditActor[]
  total: number
  truncated: boolean
}

function queryString(filters: AuditFilters): string {
  const params = new URLSearchParams()
  if (filters.actor) params.set('actor', filters.actor)
  if (filters.action) params.set('action', filters.action)
  if (filters.from) params.set('from', filters.from)
  if (filters.to) params.set('to', filters.to)
  const value = params.toString()
  return value ? `?${value}` : ''
}

/** Журнал за выбранный период; без фильтров сервер отдаёт последние 7 дней. */
export const auditQueryOptions = (filters: AuditFilters) =>
  queryOptions({
    queryKey: ['audit-log', filters],
    queryFn: async ({ signal }) =>
      apiGet<AuditPage>(`/admin/audit-log${queryString(filters)}`, signal),
    retry: false,
  })

/** CSV за те же фильтры; выгрузка добавляет в журнал запись «Экспорт». */
export function exportAuditLog(filters: AuditFilters) {
  return apiDownload('/admin/audit-log/export', {
    actor: filters.actor,
    action: filters.action,
    from: filters.from,
    to: filters.to,
  })
}

export function actorValue(actor: AuditActor): string {
  return `${actor.kind}:${actor.id}`
}
