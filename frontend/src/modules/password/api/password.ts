import { apiPost, type ApiErrorBody } from '@/common/api-client'
import type { Subject } from '@/modules/session'

/** `invitation` — первый пароль по приглашению; `reset` — восстановление. */
export type LinkFlow = 'invitation' | 'reset'

const PATHS: Record<LinkFlow, { preview: string; submit: string }> = {
  invitation: { preview: '/invitations/preview', submit: '/invitations/accept' },
  reset: { preview: '/password-reset/preview', submit: '/password-reset/complete' },
}

export type PreviewResult =
  | { kind: 'valid'; email: string; name?: string }
  | { kind: 'expired' }
  | { kind: 'failed'; status: number }

export type SubmitResult =
  | { kind: 'success'; subject: Subject }
  | { kind: 'invalid-password'; message: string }
  | { kind: 'expired' }
  | { kind: 'failed'; status: number }

export type ResetRequestResult =
  | { kind: 'accepted' }
  | { kind: 'cooldown'; retryAfterSeconds: number }
  | { kind: 'invalid-email' }
  | { kind: 'delivery-failed' }
  | { kind: 'failed'; status: number }

const PASSWORD_ERRORS: Record<string, string> = {
  'password must contain at least 8 characters': 'Пароль должен содержать минимум 8 символов.',
  'password must contain a letter': 'Пароль должен содержать хотя бы одну букву.',
  'password must contain a decimal digit': 'Пароль должен содержать хотя бы одну цифру.',
  'passwords do not match': 'Пароли не совпадают.',
}

export async function previewLink(
  flow: LinkFlow,
  token: string,
  signal?: AbortSignal,
): Promise<PreviewResult> {
  const response = await apiPost<{ email?: string; name?: string }>(
    PATHS[flow].preview,
    { token },
    signal,
  )
  if (response.status === 200 && response.data?.email) {
    return { kind: 'valid', email: response.data.email, name: response.data.name }
  }
  if (response.status === 410) {
    return { kind: 'expired' }
  }
  return { kind: 'failed', status: response.status }
}

export async function submitPassword(
  flow: LinkFlow,
  token: string,
  password: string,
  confirmation: string,
): Promise<SubmitResult> {
  const response = await apiPost<{ subject?: Subject } & ApiErrorBody>(PATHS[flow].submit, {
    token,
    password,
    password_confirmation: confirmation,
  })
  const data = response.data
  if (response.status === 200 && data?.subject) {
    return { kind: 'success', subject: data.subject }
  }
  if (response.status === 422 && data?.field === 'password') {
    return {
      kind: 'invalid-password',
      message: PASSWORD_ERRORS[data.detail ?? ''] ?? 'Пароль не отвечает требованиям.',
    }
  }
  if (response.status === 410) {
    return { kind: 'expired' }
  }
  return { kind: 'failed', status: response.status }
}

export async function requestPasswordReset(email: string): Promise<ResetRequestResult> {
  const response = await apiPost<ApiErrorBody>('/password-reset/request', { email })
  if (response.status === 202) {
    return { kind: 'accepted' }
  }
  if (response.status === 429 && response.data?.retry_after_seconds !== undefined) {
    return { kind: 'cooldown', retryAfterSeconds: response.data.retry_after_seconds }
  }
  if (response.status === 422) {
    return { kind: 'invalid-email' }
  }
  if (response.status === 502) {
    return { kind: 'delivery-failed' }
  }
  return { kind: 'failed', status: response.status }
}
