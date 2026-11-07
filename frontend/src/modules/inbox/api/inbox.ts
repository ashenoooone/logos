import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost, apiSend, apiUpload } from '@/common/api-client'
import type { TagRef } from '@/modules/tags'

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
  author: string | null
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
  tags: TagRef[]
}

export interface ConversationList {
  conversations: ConversationSummary[]
  unread_total: number
  last_incoming_id: number | null
  incoming_total: number
}

export interface Thread {
  conversation: { id: number; provider: 'telegram'; name: string; tags: TagRef[] }
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

export function conversationsQueryOptions(query = '') {
  const normalized = query.trim()
  return queryOptions({
    queryKey: ['conversations', 'list', normalized],
    queryFn: async ({ signal }) => {
      const search = normalized ? `?q=${encodeURIComponent(normalized)}` : ''
      const response = await apiGet<ConversationList>(`/conversations${search}`, signal)
      return toResult(response.status, response.data)
    },
    refetchInterval: POLL_MS,
    retry: false,
  })
}

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

// #7: сортировка и фильтры. Значения внутри фильтра — ИЛИ, разные фильтры — И (ADR-0007).
export type Sort = 'newest' | 'oldest' | 'unread'

export interface Filters {
  channel: 'telegram'[]
  tag: number[]
  status: ('unread' | 'read')[]
}

export interface SavedFilter {
  id: number
  name: string
  filters: Filters
}

export interface Preferences {
  sort: Sort
  saved_filters: SavedFilter[]
}

export const NO_FILTERS: Filters = { channel: [], tag: [], status: [] }

export function hasFilters(filters: Filters): boolean {
  return filters.channel.length + filters.tag.length + filters.status.length > 0
}

/** Id диалогов, прошедших фильтры, в порядке выбранной сортировки. */
export function arrange(items: ConversationSummary[], sort: Sort, filters: Filters): number[] {
  const time = (item: ConversationSummary) => Date.parse(item.last_message_at)
  const byNewest = (a: ConversationSummary, b: ConversationSummary) => time(b) - time(a) || b.id - a.id
  const compare: Record<Sort, typeof byNewest> = {
    newest: byNewest,
    oldest: (a, b) => -byNewest(a, b),
    unread: (a, b) => b.unread_count - a.unread_count || byNewest(a, b),
  }
  // ponytail: фильтрация на клиенте по полному списку; на сервер — когда появится постраничность.
  return items
    .filter(
      (item) =>
        (filters.channel.length === 0 || filters.channel.includes(item.provider)) &&
        (filters.tag.length === 0 || item.tags.some((tag) => filters.tag.includes(tag.id))) &&
        (filters.status.length === 0 || filters.status.includes(item.unread_count > 0 ? 'unread' : 'read')),
    )
    .sort(compare[sort])
    .map((item) => item.id)
}

export const preferencesQueryOptions = queryOptions({
  queryKey: ['inbox-preferences'],
  queryFn: async ({ signal }) => {
    const response = await apiGet<Preferences>('/conversations/preferences', signal)
    return toResult(response.status, response.data)
  },
  retry: false,
})

export async function saveSort(sort: Sort): Promise<Result<Preferences>> {
  const response = await apiSend<Preferences>('PUT', '/conversations/preferences/sort', { sort })
  return toResult(response.status, response.data)
}

export async function saveFilter(name: string, filters: Filters): Promise<Result<Preferences>> {
  const response = await apiPost<Preferences>('/conversations/saved-filters', { name, filters })
  return toResult(response.status, response.data)
}

export async function deleteSavedFilter(id: number): Promise<Result<Preferences>> {
  const response = await apiSend<Preferences>('DELETE', `/conversations/saved-filters/${id}`)
  return toResult(response.status, response.data)
}
