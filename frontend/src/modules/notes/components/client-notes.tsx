import {
  Alert,
  Badge,
  Button,
  Group,
  Loader,
  Paper,
  ScrollArea,
  Select,
  Stack,
  Text,
  Textarea,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'

import { failureMessage } from '@/common/api-client'
import { useSession } from '@/modules/session'

import {
  createNote,
  deleteNote,
  MAX_NOTE_LENGTH,
  notesQueryOptions,
  updateNote,
  type Note,
  type NoteResponse,
  type NoteVisibility,
} from '../api/notes'

const VISIBILITY_LABELS: Record<NoteVisibility, string> = {
  team: 'Вся команда',
  private: 'Только я',
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Вкладка «Заметки» карточки клиента (#14): форма сверху, список от новых.
 * Чужие заметки только читаются; «Только я» не показывается другим менеджерам.
 */
export function ClientNotes({ conversationId }: { conversationId: number }) {
  const { setSubject } = useSession()
  const queryClient = useQueryClient()
  const query = useQuery(notesQueryOptions(conversationId))
  const [text, setText] = useState('')
  const [visibility, setVisibility] = useState<NoteVisibility>('team')
  const [editing, setEditing] = useState<Note | null>(null)
  const [pending, setPending] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const unauthorized = query.data?.status === 401
  useEffect(() => {
    if (unauthorized) {
      setSubject(null)
    }
  }, [unauthorized, setSubject])

  const notes = query.data?.status === 200 ? (query.data.data.notes ?? []) : []
  const failed = query.data !== undefined && query.data.status !== 200 && !unauthorized
  const error = text.length > MAX_NOTE_LENGTH ? `Не больше ${MAX_NOTE_LENGTH} символов` : null
  const canSave = text.trim() !== '' && !error && !pending

  function reset() {
    setText('')
    setVisibility('team')
    setEditing(null)
  }

  function startEditing(note: Note) {
    setEditing(note)
    setText(note.text)
    setVisibility(note.visibility)
    setNotice(null)
  }

  /** Общая обработка ответа: список заметок, конфликт версий и выход по 401. */
  function handle(response: { status: number; data: NoteResponse }, success: string[]) {
    if (response.status === 401) {
      setSubject(null)
      return false
    }
    if (response.status === 409 && response.data.note) {
      const current = response.data.note
      setEditing(current)
      setText(current.text)
      setVisibility(current.visibility)
      setNotice(
        'Заметку изменили, пока вы её читали. Показана актуальная версия — проверьте текст и сохраните снова.',
      )
      void query.refetch()
      return false
    }
    if (response.status === 403) {
      setNotice('Менять и удалять можно только свои заметки.')
      void query.refetch()
      return false
    }
    if (success.includes(String(response.status)) && response.data.notes) {
      queryClient.setQueryData(notesQueryOptions(conversationId).queryKey, {
        status: response.status,
        data: response.data,
      })
      return true
    }
    setNotice(failureMessage(response.status))
    return false
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!canSave) {
      return
    }
    setPending(true)
    setNotice(null)
    try {
      const response = editing
        ? await updateNote(conversationId, editing.id, text.trim(), visibility, editing.version)
        : await createNote(conversationId, text.trim(), visibility)
      if (handle(response, editing ? ['200'] : ['201'])) {
        reset()
      }
    } catch {
      setNotice(failureMessage())
    } finally {
      setPending(false)
    }
  }

  async function remove(note: Note) {
    if (!window.confirm('Удалить заметку?')) {
      return
    }
    setNotice(null)
    try {
      const response = await deleteNote(conversationId, note.id)
      if (handle(response, ['200']) && editing?.id === note.id) {
        reset()
      }
    } catch {
      setNotice(failureMessage())
    }
  }

  if (query.isPending) {
    return <Loader m="auto" aria-label="Загрузка заметок" />
  }

  return (
    <ScrollArea style={{ flex: 1 }} px="md">
      <Stack gap="md" py="md" maw={720}>
        {notice && (
          <Alert color="yellow" role="alert" withCloseButton onClose={() => setNotice(null)}>
            {notice}
          </Alert>
        )}
        {failed && (
          <Alert color="red" role="alert" title="Не удалось загрузить заметки">
            <Group gap="xs">
              <Text size="sm">{failureMessage(query.data?.status)}</Text>
              <Button size="xs" variant="default" onClick={() => void query.refetch()}>
                Повторить
              </Button>
            </Group>
          </Alert>
        )}

        <form onSubmit={save} noValidate>
          <Stack gap="sm">
            <Textarea
              aria-label={editing ? 'Изменить заметку' : 'Новая заметка'}
              label={editing ? 'Изменить заметку' : 'Новая заметка'}
              placeholder="Что важно помнить о клиенте"
              autosize
              minRows={3}
              maxRows={8}
              value={text}
              error={error}
              onChange={(event) => setText(event.currentTarget.value)}
            />
            <Group justify="space-between" align="flex-end">
              <Select
                label="Видимость"
                allowDeselect={false}
                data={[
                  { value: 'team', label: VISIBILITY_LABELS.team },
                  { value: 'private', label: VISIBILITY_LABELS.private },
                ]}
                value={visibility}
                onChange={(value) => setVisibility(value === 'private' ? 'private' : 'team')}
                w={180}
              />
              <Group gap="sm">
                {editing && (
                  <Button variant="default" onClick={reset} disabled={pending}>
                    Отмена
                  </Button>
                )}
                <Button type="submit" loading={pending} disabled={!canSave}>
                  Сохранить
                </Button>
              </Group>
            </Group>
          </Stack>
        </form>

        {!failed && notes.length === 0 && (
          <Text size="sm" c="dimmed">
            Пока нет заметок.
          </Text>
        )}

        {notes.map((note) => (
          <Paper key={note.id} withBorder p="md">
            <Stack gap={6}>
              <Group justify="space-between" wrap="nowrap" gap="sm">
                <Group gap={6} wrap="nowrap">
                  <Text size="sm" fw={600}>
                    {note.author ?? 'Неизвестный автор'}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {formatDate(note.created_at)}
                  </Text>
                  {note.visibility === 'private' && (
                    <Badge size="xs" variant="light" color="gray">
                      {VISIBILITY_LABELS.private}
                    </Badge>
                  )}
                </Group>
                {note.editable && (
                  <Group gap="xs" wrap="nowrap">
                    <Button size="compact-xs" variant="subtle" onClick={() => startEditing(note)}>
                      Изменить
                    </Button>
                    <Button
                      size="compact-xs"
                      variant="subtle"
                      color="red"
                      onClick={() => void remove(note)}
                    >
                      Удалить
                    </Button>
                  </Group>
                )}
              </Group>
              <Text size="sm" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
                {note.text}
              </Text>
            </Stack>
          </Paper>
        ))}
      </Stack>
    </ScrollArea>
  )
}
