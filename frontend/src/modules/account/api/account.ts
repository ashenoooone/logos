import { queryOptions } from '@tanstack/react-query'

import { apiPost, type ApiErrorBody } from '@/common/api-client'
import type { Subject } from '@/modules/session'

export type FieldErrors = Partial<Record<string, string>>

export type SaveResult<T> =
  | { kind: 'success'; value: T }
  | { kind: 'invalid'; errors: FieldErrors }
  | { kind: 'unauthorized' }
  | { kind: 'failed'; status: number }

const MESSAGES: Record<string, string> = {
  'Name must not be blank': 'Укажите имя.',
  'Invalid email address': 'Некорректный email.',
  'Email is unchanged': 'Это ваш текущий email.',
  'Email is already taken': 'Email занят.',
  'Current password is required': 'Укажите текущий пароль.',
  'Invalid current password': 'Неверный текущий пароль.',
  'passwords do not match': 'Пароли не совпадают.',
  'password must contain at least 8 characters': 'Пароль должен содержать минимум 8 символов.',
  'password must contain a letter': 'Пароль должен содержать хотя бы одну букву.',
  'password must contain a decimal digit': 'Пароль должен содержать хотя бы одну цифру.',
}

async function save<D, T>(
  path: string,
  body: unknown,
  ok: number,
  pick: (data: D) => T,
): Promise<SaveResult<T>> {
  const response = await apiPost<D & ApiErrorBody>(path, body)
  const data = response.data
  if (response.status === ok) {
    return { kind: 'success', value: pick(data) }
  }
  if (response.status === 422 && data?.field) {
    let message = MESSAGES[data.detail ?? ''] ?? 'Проверьте значение.'
    if (data.field === 'current_password' && data.attempts_remaining !== undefined) {
      message += ` Осталось попыток: ${data.attempts_remaining}.`
    }
    return { kind: 'invalid', errors: { [data.field]: message } }
  }
  if (response.status === 423) {
    const minutes = Math.ceil((data?.retry_after_seconds ?? 0) / 60)
    return {
      kind: 'invalid',
      errors: { current_password: `Слишком много попыток. Повторите через ${minutes} мин.` },
    }
  }
  if (response.status === 502) {
    // Только /account/email: письмо подтверждения не принято SMTP.
    return { kind: 'invalid', errors: { email: 'Не удалось отправить письмо. Повторите попытку.' } }
  }
  if (response.status === 401) {
    return { kind: 'unauthorized' }
  }
  return { kind: 'failed', status: response.status }
}

export function changeName(name: string) {
  return save('/account/name', { name }, 200, (d: { subject: Subject }) => d.subject)
}

export function requestEmailChange(email: string) {
  return save('/account/email', { email }, 202, (d: { pending_email: string }) => d.pending_email)
}

export async function changePassword(body: {
  current_password: string
  new_password: string
  new_password_confirmation: string
  sign_out_other_devices: boolean
}) {
  return save('/account/password', body, 200, () => undefined)
}

export type ConfirmResult =
  | { kind: 'confirmed'; managerId: number; email: string }
  | { kind: 'expired' }
  | { kind: 'taken' }
  | { kind: 'failed'; status: number }

export async function confirmEmail(token: string): Promise<ConfirmResult> {
  const response = await apiPost<{ manager_id?: number; email?: string }>(
    '/account/email/confirm',
    { token },
  )
  const data = response.data
  if (response.status === 200 && data?.email && data.manager_id !== undefined) {
    return { kind: 'confirmed', managerId: data.manager_id, email: data.email }
  }
  if (response.status === 410) {
    return { kind: 'expired' }
  }
  if (response.status === 409) {
    return { kind: 'taken' }
  }
  return { kind: 'failed', status: response.status }
}

// Подтверждение гасит ссылку: один запрос на токен, без signal (повторный монтаж
// в StrictMode не должен отменить и повторить POST), без повторов и рефетча.
export const confirmEmailQueryOptions = (token: string) =>
  queryOptions({
    queryKey: ['account', 'email-confirmation', token],
    queryFn: () => confirmEmail(token),
    retry: false,
    staleTime: Infinity,
    gcTime: Infinity,
  })
