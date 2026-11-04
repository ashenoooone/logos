import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost, type ApiErrorBody } from '@/common/api-client'

export interface Channel {
  provider: 'telegram'
  name: string | null
  bot_username: string | null
  status: 'connected' | 'error' | 'disconnected'
  error: 'token_invalid' | 'conflict' | null
  updated_at: string | null
}

export type Result<T> =
  | { kind: 'success'; value: T }
  | { kind: 'invalid-token' }
  | { kind: 'already-connected' }
  | { kind: 'unavailable' }
  | { kind: 'unauthorized' }
  | { kind: 'failed'; status: number }

type Body = { channel?: Channel; bot_username?: string } & ApiErrorBody

function toResult<T>(status: number, data: Body | null, pick: (data: Body) => T | undefined) {
  const value = data ? pick(data) : undefined
  if (status === 200 && value !== undefined) {
    return { kind: 'success', value } as const
  }
  if (status === 422 && data?.field === 'token') {
    return { kind: 'invalid-token' } as const
  }
  if (status === 409) {
    return { kind: 'already-connected' } as const
  }
  if (status === 502) {
    return { kind: 'unavailable' } as const
  }
  if (status === 401) {
    return { kind: 'unauthorized' } as const
  }
  return { kind: 'failed', status } as const
}

export async function getChannel(signal?: AbortSignal): Promise<Result<Channel>> {
  const response = await apiGet<Body>('/admin/channels', signal)
  return toResult(response.status, response.data, (data) => data.channel)
}

// Опрос раз в 10 с: сбой канала обнаруживает фоновый процесс бэкенда.
export const channelQueryOptions = queryOptions({
  queryKey: ['channel'],
  queryFn: ({ signal }) => getChannel(signal),
  refetchInterval: 10_000,
  retry: false,
})

export async function checkToken(token: string): Promise<Result<string>> {
  const response = await apiPost<Body>('/admin/channels/telegram/check', { token })
  return toResult(response.status, response.data, (data) => data.bot_username)
}

export async function connectChannel(token: string, name: string): Promise<Result<Channel>> {
  const response = await apiPost<Body>('/admin/channels/telegram', { token, name })
  return toResult(response.status, response.data, (data) => data.channel)
}

export async function disconnectChannel(): Promise<Result<Channel>> {
  const response = await apiPost<Body>('/admin/channels/telegram/disconnect')
  return toResult(response.status, response.data, (data) => data.channel)
}
