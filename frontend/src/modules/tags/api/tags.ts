import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost, apiSend, type ApiResponse } from '@/common/api-client'

export interface TagRef {
  id: number
  name: string
}

export interface Tag extends TagRef {
  standard: boolean
  own: boolean
  author: string | null
  conversation_count: number
}

type TagList = { tags?: Tag[] }
type ConversationTagList = { tags?: TagRef[] }

/** Все теги компании; менеджеру — с пометкой `own`. `null` в data — 401 или сбой. */
export const tagsQueryOptions = queryOptions({
  queryKey: ['tags'],
  queryFn: async ({ signal }) => apiGet<TagList>('/tags', signal),
  retry: false,
})

export const adminTagsQueryOptions = queryOptions({
  queryKey: ['admin-tags'],
  queryFn: async ({ signal }) => apiGet<TagList>('/admin/tags', signal),
  retry: false,
})

/** Ставит тег по имени: существующий без учёта регистра или новый. */
export function attachTag(conversationId: number, name: string): Promise<ApiResponse<ConversationTagList>> {
  return apiPost(`/conversations/${conversationId}/tags`, { name })
}

export function detachTag(conversationId: number, tagId: number): Promise<ApiResponse<ConversationTagList>> {
  return apiSend('DELETE', `/conversations/${conversationId}/tags/${tagId}`)
}

export function deleteOwnTag(tagId: number): Promise<ApiResponse> {
  return apiSend('DELETE', `/tags/${tagId}`)
}

export function createStandardTag(name: string): Promise<ApiResponse<TagList>> {
  return apiPost('/admin/tags', { name })
}

export function renameTag(tagId: number, name: string): Promise<ApiResponse<TagList>> {
  return apiSend('PATCH', `/admin/tags/${tagId}`, { name })
}

export function deleteTag(tagId: number): Promise<ApiResponse<TagList>> {
  return apiSend('DELETE', `/admin/tags/${tagId}`)
}

const COLORS = ['red', 'yellow', 'violet', 'teal', 'orange', 'grape', 'cyan', 'lime', 'pink', 'indigo']

export function tagColor(id: number): string {
  return COLORS[id % COLORS.length]
}

/** Подтверждение удаления тега: он снимется со всех диалогов. */
export function confirmTagDelete(tag: Tag): boolean {
  const used = tag.conversation_count > 0 ? ` Тег снимется с диалогов: ${tag.conversation_count}.` : ''
  return window.confirm(`Удалить тег «${tag.name}»?${used}`)
}
