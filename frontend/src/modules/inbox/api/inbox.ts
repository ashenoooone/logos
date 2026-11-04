import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost, apiUpload } from '@/common/api-client'

// Пределы бэкенда (Bot API): текст 4096, подпись к файлу 1024, файл до 20 МБ.
export const MAX_TEXT_LENGTH = 4096
export const MAX_CAPTION_LENGTH = 1024
export const MAX_FILE_BYTES = 20 * 1024 * 1024

// ADR-0007: новые сообщения — опросом раз в 3–5 с.
const POLL_MS = 4_000

export interface InboxFile {
  name: string
  size: number | null
  available: boolean
}

export interface Message {
  id: number
  direction: 'in' | 'out'
  kind: 'text' | 'photo' | 'document' | 'unsupported'
  text: string | null
  file: InboxFile | null
  status: 'sending' | 'delivered' | 'failed' | null
  created_at: string
}

export interface ConversationSummary {
  id: number
  provider: 'telegram'
  name: string
  last_message_at: string
  unread_count: number
  last_message: Message | null
}

export interface ConversationList {
  conversations: ConversationSummary[]
  unread_total: number
  last_incoming_id: number | null
}

export interface Thread {
  conversation: { id: number; provider: 'telegram'; name: string }
  messages: Message[]
}

export type Result<T> =
  | { kind: 'success'; value: T }
  | { kind: 'unauthorized' }
  | { kind: 'not-found' }
  | { kind: 'failed'; status: number }

function toResult<T>(status: number, value: T | null | undefined): Result<T> {
  if (status === 200 && value) {
    return { kind: 'success', value }
  }
  if (status === 401) {
    return { kind: 'unauthorized' }
  }
  if (status === 404) {
    return { kind: 'not-found' }
  }
  return { kind: 'failed', status }
}

export const conversationsQueryOptions = queryOptions({
  queryKey: ['conversations'],
  queryFn: async ({ signal }) => {
    const response = await apiGet<ConversationList>('/conversations', signal)
    return toResult(response.status, response.data)
  },
  refetchInterval: POLL_MS,
  retry: false,
})

export function threadQueryOptions(id: number) {
  return queryOptions({
    queryKey: ['conversations', id],
    queryFn: async ({ signal }) => {
      const response = await apiGet<Thread>(`/conversations/${id}/messages`, signal)
      return toResult(response.status, response.data)
    },
    refetchInterval: POLL_MS,
    retry: false,
  })
}

export async function markRead(id: number): Promise<void> {
  await apiPost(`/conversations/${id}/read`)
}

type MessageBody = { message?: Message }

export async function sendReply(id: number, text: string): Promise<Result<Message>> {
  const response = await apiPost<MessageBody>(`/conversations/${id}/messages`, { text })
  return toResult(response.status, response.data?.message)
}

export async function sendFile(id: number, file: File, text: string): Promise<Result<Message>> {
  const query = new URLSearchParams({ name: file.name, text })
  const response = await apiUpload<MessageBody>(`/conversations/${id}/files?${query}`, file)
  return toResult(response.status, response.data?.message)
}

export async function retryMessage(id: number): Promise<Result<Message>> {
  const response = await apiPost<MessageBody>(`/messages/${id}/retry`)
  return toResult(response.status, response.data?.message)
}

export function attachmentUrl(messageId: number): string {
  return `/messages/${messageId}/attachment`
}
