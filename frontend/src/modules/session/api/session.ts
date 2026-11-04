import { apiGet, apiPost, type ApiErrorBody } from '@/common/api-client'

export type Subject =
  | { type: 'administrator' }
  | { type: 'manager'; id: number; name: string; email: string }

export type LoginKind = Subject['type']

export type LoginResult =
  | { kind: 'success'; subject: Subject }
  | { kind: 'invalid'; attemptsRemaining?: number }
  | { kind: 'locked'; retryAfterSeconds?: number }
  | { kind: 'failed'; status: number }

/** Текущий субъект по cookie сессии; `null` — сессии нет. */
export async function fetchMe(signal?: AbortSignal): Promise<Subject | null> {
  const response = await apiGet<{ subject: Subject }>('/auth/me', signal)
  if (response.status === 200 && response.data?.subject) {
    return response.data.subject
  }
  if (response.status === 401) {
    return null
  }
  throw new Error(`GET /auth/me: HTTP ${response.status}`)
}

export async function login(
  kind: LoginKind,
  identifier: string,
  password: string,
  remember: boolean,
): Promise<LoginResult> {
  const path = kind === 'administrator' ? '/auth/admin/login' : '/auth/manager/login'
  const body =
    kind === 'administrator'
      ? { login: identifier, password, remember }
      : { email: identifier, password, remember }
  const response = await apiPost<{ subject?: Subject } & ApiErrorBody>(path, body)
  const data = response.data

  if (response.status === 200 && data?.subject) {
    return { kind: 'success', subject: data.subject }
  }
  if (response.status === 401) {
    return { kind: 'invalid', attemptsRemaining: data?.attempts_remaining }
  }
  if (response.status === 423) {
    return { kind: 'locked', retryAfterSeconds: data?.retry_after_seconds }
  }
  return { kind: 'failed', status: response.status }
}

export async function logout(): Promise<boolean> {
  const response = await apiPost('/auth/logout')
  return response.status === 204
}
