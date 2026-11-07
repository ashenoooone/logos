import { queryOptions } from '@tanstack/react-query'

import { apiPost, type ApiErrorBody } from '@/common/api-client'
import type { Subject } from '@/modules/session'

/** Первый пароль менеджера по одноразовому приглашению. */
export type LinkFlow = 'invitation'

const PATHS: Record<LinkFlow, { preview: string; submit: string }> = {
  invitation: { preview: '/invitations/preview', submit: '/invitations/accept' },
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

export const previewLinkQueryOptions = (flow: LinkFlow, token: string) =>
  queryOptions({
    queryKey: ['password-link', flow, token],
    queryFn: ({ signal }) => previewLink(flow, token, signal),
    retry: false,
    staleTime: Infinity,
  })

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

