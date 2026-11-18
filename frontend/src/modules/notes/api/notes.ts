import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost, apiSend, type ApiResponse } from '@/common/api-client'

// Предел бэкенда: текст заметки 1–2000 символов после trim.
export const MAX_NOTE_LENGTH = 2000

export type NoteVisibility = 'team' | 'private'

export interface Note {
  id: number
  text: string
  visibility: NoteVisibility
  author: string | null
  own: boolean
  editable: boolean
  version: number
  created_at: string
  updated_at: string
}

export type NoteList = { notes: Note[] }

/** Успех — список заметок; при `409` — актуальная версия в `note`. */
export type NoteResponse = Partial<NoteList> & { note?: Note; detail?: string }

/** Заметки диалога, новые сверху; приватные чужие сервер не возвращает. */
export function notesQueryOptions(conversationId: number) {
  return queryOptions({
    queryKey: ['conversation-notes', conversationId],
    queryFn: async ({ signal }) =>
      apiGet<NoteResponse>(`/conversations/${conversationId}/notes`, signal),
    retry: false,
  })
}

export function createNote(
  conversationId: number,
  text: string,
  visibility: NoteVisibility,
): Promise<ApiResponse<NoteResponse>> {
  return apiPost(`/conversations/${conversationId}/notes`, { text, visibility })
}

export function updateNote(
  conversationId: number,
  noteId: number,
  text: string,
  visibility: NoteVisibility,
  version: number,
): Promise<ApiResponse<NoteResponse>> {
  return apiSend('PUT', `/conversations/${conversationId}/notes/${noteId}`, {
    text,
    visibility,
    version,
  })
}

export function deleteNote(
  conversationId: number,
  noteId: number,
): Promise<ApiResponse<NoteResponse>> {
  return apiSend('DELETE', `/conversations/${conversationId}/notes/${noteId}`)
}
