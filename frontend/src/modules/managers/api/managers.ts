import { apiGet, apiPost, type ApiErrorBody } from '@/common/api-client'

export interface Manager {
  id: number
  name: string
  email: string
  role: 'manager'
  status: 'pending' | 'active'
  created_at: string
}

export type ListResult =
  | { kind: 'success'; managers: Manager[] }
  | { kind: 'unauthorized' }
  | { kind: 'failed'; status: number }

export type InvitationResult =
  | { kind: 'sent'; manager: Manager }
  | { kind: 'delivery-failed'; manager: Manager }
  | { kind: 'field'; field: 'name' | 'email'; message: string }
  | { kind: 'already-accepted' }
  | { kind: 'not-found' }
  | { kind: 'unauthorized' }
  | { kind: 'failed'; status: number }

type InvitationBody = { manager?: Manager } & ApiErrorBody

const EMAIL_TAKEN = 'A manager with this email already exists'

export async function listManagers(signal?: AbortSignal): Promise<ListResult> {
  const response = await apiGet<{ managers?: Manager[] }>('/admin/managers', signal)
  if (response.status === 200 && response.data?.managers) {
    return { kind: 'success', managers: response.data.managers }
  }
  if (response.status === 401) {
    return { kind: 'unauthorized' }
  }
  return { kind: 'failed', status: response.status }
}

export async function createManager(name: string, email: string): Promise<InvitationResult> {
  const response = await apiPost<InvitationBody>('/admin/managers', { name, email })
  return toInvitationResult(response.status, response.data, 201)
}

/** Повтор приглашения ожидающему менеджеру; новый `email` исправляет опечатку. */
export async function resendInvitation(id: number, email: string): Promise<InvitationResult> {
  const response = await apiPost<InvitationBody>(`/admin/managers/${id}/invitation`, { email })
  return toInvitationResult(response.status, response.data, 200)
}

function toInvitationResult(
  status: number,
  data: InvitationBody | null,
  successStatus: number,
): InvitationResult {
  if (status === successStatus && data?.manager) {
    return { kind: 'sent', manager: data.manager }
  }
  if (status === 502 && data?.manager) {
    return { kind: 'delivery-failed', manager: data.manager }
  }
  if (status === 422 && data?.field === 'name') {
    return { kind: 'field', field: 'name', message: 'Укажите имя и фамилию' }
  }
  if (status === 422 && data?.field === 'email') {
    return {
      kind: 'field',
      field: 'email',
      message: data.detail === EMAIL_TAKEN ? 'Этот email уже есть в системе' : 'Некорректный email',
    }
  }
  if (status === 409) {
    return { kind: 'already-accepted' }
  }
  if (status === 404) {
    return { kind: 'not-found' }
  }
  if (status === 401) {
    return { kind: 'unauthorized' }
  }
  return { kind: 'failed', status }
}
