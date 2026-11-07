import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost, type ApiErrorBody } from '@/common/api-client'

export type Subject =
  | { type: 'administrator' }
  | { type: 'manager'; id: number; name: string; email: string }

export type LoginResult =
  | { kind: 'success'; subject: Subject }
  | { kind: 'invalid'; attemptsRemaining?: number }
  | { kind: 'locked'; retryAfterSeconds: number }
  | { kind: 'failed'; status: number }

export type LoginKind = Subject['type']

export type OtpRequestResult =
  | { kind: 'accepted' }
  | { kind: 'cooldown'; retryAfterSeconds: number }
  | { kind: 'invalid-email' }
  | { kind: 'delivery-failed' }
  | { kind: 'failed'; status: number }

export type OtpVerifyResult =
  | { kind: 'success'; subject: Subject }
  | { kind: 'invalid' }
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

/** Кэш сессии: источник истины для `useSession`; обновляется через `setQueryData`. */
export const meQueryOptions = queryOptions({
  queryKey: ['session', 'me'],
  queryFn: ({ signal }) => fetchMe(signal),
  retry: false,
  staleTime: Infinity,
})

export async function requestManagerOtp(email: string): Promise<OtpRequestResult> {
  const response = await apiPost<ApiErrorBody>('/auth/manager/otp/request', { email })
  if (response.status === 202) return { kind: 'accepted' }
  if (response.status === 429) {
    return { kind: 'cooldown', retryAfterSeconds: response.data?.retry_after_seconds ?? 60 }
  }
  if (response.status === 422) return { kind: 'invalid-email' }
  if (response.status === 503) return { kind: 'delivery-failed' }
  return { kind: 'failed', status: response.status }
}

export async function verifyManagerOtp(
  email: string,
  code: string,
  remember: boolean,
): Promise<OtpVerifyResult> {
  const response = await apiPost<{ subject?: Subject } & ApiErrorBody>(
    '/auth/manager/otp/verify',
    { email, code, remember },
  )
  if (response.status === 200 && response.data?.subject) {
    return { kind: 'success', subject: response.data.subject }
  }
  if (response.status === 401) return { kind: 'invalid' }
  return { kind: 'failed', status: response.status }
}

export async function login(
  identifier: string,
  password: string,
  remember: boolean,
): Promise<LoginResult> {
  const response = await apiPost<{ subject?: Subject } & ApiErrorBody>('/auth/admin/login', {
    login: identifier,
    password,
    remember,
  })
  const data = response.data
  if (response.status === 200 && data?.subject) return { kind: 'success', subject: data.subject }
  if (response.status === 401) return { kind: 'invalid', attemptsRemaining: data?.attempts_remaining }
  if (response.status === 423) {
    return { kind: 'locked', retryAfterSeconds: data?.retry_after_seconds ?? 0 }
  }
  return { kind: 'failed', status: response.status }
}


export async function logout(): Promise<boolean> {
  const response = await apiPost('/auth/logout')
  return response.status === 204
}
