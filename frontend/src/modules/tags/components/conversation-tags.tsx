import { ActionIcon, Button, Group, Popover, Stack, Text, TextInput, UnstyledButton } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { failureMessage, type ApiResponse } from '@/common/api-client'
import { useSession } from '@/modules/session'

import {
  attachTag,
  confirmTagDelete,
  deleteOwnTag,
  detachTag,
  tagsQueryOptions,
  type Tag,
  type TagRef,
} from '../api/tags'
import { TagBadge } from './tag-badge'

const fold = (value: string) => value.trim().toLocaleLowerCase('ru')

/**
 * «Теги:» в шапке диалога (#8): снять тег, поставить существующий или создать новый.
 * В подсказках — стандартные и свои теги (ADR-0007); поиск без учёта регистра.
 */
export function ConversationTags({ conversationId, tags }: { conversationId: number; tags: TagRef[] }) {
  const { setSubject } = useSession()
  const queryClient = useQueryClient()
  const all = useQuery(tagsQueryOptions)
  const [opened, setOpened] = useState(false)
  const [search, setSearch] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const known = all.data?.status === 200 ? (all.data.data.tags ?? []) : []
  const attached = new Set(tags.map((tag) => tag.id))
  const query = fold(search)
  const suggestions = known.filter(
    (tag) => (tag.standard || tag.own) && !attached.has(tag.id) && fold(tag.name).includes(query),
  )
  const exact = known.find((tag) => fold(tag.name) === query)

  async function run(action: () => Promise<ApiResponse>) {
    setPending(true)
    setError(null)
    try {
      const response = await action()
      if (response.status === 401) {
        setSubject(null)
      } else if (response.status === 403) {
        setError('Удалять можно только свои теги.')
      } else if (response.status !== 200) {
        setError(failureMessage(response.status))
      } else {
        setSearch('')
        void queryClient.invalidateQueries({ queryKey: ['conversations'] })
        void queryClient.invalidateQueries({ queryKey: tagsQueryOptions.queryKey })
      }
    } catch {
      setError(failureMessage())
    }
    setPending(false)
  }

  function remove(tag: Tag) {
    if (confirmTagDelete(tag)) {
      void run(() => deleteOwnTag(tag.id))
    }
  }

  return (
    <Group gap={6} px="md" py={6} style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}>
      <Text size="sm" c="dimmed">
        Теги:
      </Text>
      {tags.map((tag) => (
        <TagBadge key={tag.id} tag={tag} onRemove={() => void run(() => detachTag(conversationId, tag.id))} />
      ))}
      <Popover opened={opened} onChange={setOpened} position="bottom-start" width={300} trapFocus>
        <Popover.Target>
          <Button size="compact-xs" variant="light" onClick={() => setOpened((value) => !value)}>
            + тег
          </Button>
        </Popover.Target>
        <Popover.Dropdown>
          <Stack gap={4}>
            <TextInput
              aria-label="Найти или создать тег"
              placeholder="Найти или создать тег"
              size="xs"
              maxLength={50}
              value={search}
              onChange={(event) => setSearch(event.currentTarget.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && query && !event.nativeEvent.isComposing) {
                  event.preventDefault()
                  void run(() => attachTag(conversationId, exact?.name ?? search))
                }
              }}
            />
            {suggestions.map((tag) => (
              <Group key={tag.id} gap={4} wrap="nowrap" justify="space-between">
                <UnstyledButton
                  disabled={pending}
                  onClick={() => void run(() => attachTag(conversationId, tag.name))}
                  style={{ flex: 1, minWidth: 0 }}
                >
                  <Text size="sm" truncate>
                    {tag.name}{' '}
                    <Text span size="xs" c="dimmed">
                      · {tag.conversation_count} {tag.standard ? '· стандартный' : ''}
                    </Text>
                  </Text>
                </UnstyledButton>
                {tag.own && (
                  <ActionIcon
                    size="sm"
                    variant="subtle"
                    color="red"
                    aria-label={`Удалить тег ${tag.name}`}
                    onClick={() => remove(tag)}
                  >
                    ×
                  </ActionIcon>
                )}
              </Group>
            ))}
            {query && !suggestions.some((tag) => fold(tag.name) === query) && !(exact && attached.has(exact.id)) && (
              <Button
                size="compact-sm"
                variant="subtle"
                justify="flex-start"
                disabled={pending}
                onClick={() => void run(() => attachTag(conversationId, exact?.name ?? search))}
              >
                {exact ? `+ Добавить «${exact.name}»` : `+ Создать тег «${search.trim()}»`}
              </Button>
            )}
            {exact && attached.has(exact.id) && (
              <Text size="xs" c="dimmed">
                Тег «{exact.name}» уже стоит на диалоге
              </Text>
            )}
          </Stack>
        </Popover.Dropdown>
      </Popover>
      {error && (
        <Text size="xs" c="red" role="alert">
          {error}
        </Text>
      )}
    </Group>
  )
}
