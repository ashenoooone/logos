import { Alert, Button, Flex, Group, Loader, Paper, Stack, Text, TextInput, Title } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'

import { failureMessage, type ApiResponse } from '@/common/api-client'
import { useSession } from '@/modules/session'

import {
  adminTagsQueryOptions,
  confirmTagDelete,
  createStandardTag,
  deleteTag,
  renameTag,
  type Tag,
} from '../api/tags'
import { TagBadge } from './tag-badge'

/** Раздел администратора «Теги» (#8): стандартные теги, переименование и удаление любых тегов. */
export function TagsAdminPanel() {
  const { setSubject } = useSession()
  const queryClient = useQueryClient()
  const query = useQuery(adminTagsQueryOptions)
  const [name, setName] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const unauthorized = query.data?.status === 401
  useEffect(() => {
    if (unauthorized) {
      setSubject(null)
    }
  }, [unauthorized, setSubject])

  /** `true` — изменение сохранено. */
  async function run(action: () => Promise<ApiResponse<{ tags?: Tag[] }>>) {
    setPending(true)
    setError(null)
    let saved = false
    try {
      const response = await action()
      if (response.status === 401) {
        setSubject(null)
      } else if (response.status === 409) {
        setError('Такой тег уже есть (регистр не важен).')
      } else if (response.status === 422) {
        setError('Название тега — от 1 до 50 символов.')
      } else if (response.status !== 200) {
        setError(failureMessage(response.status))
      } else {
        queryClient.setQueryData(adminTagsQueryOptions.queryKey, response)
        saved = true
      }
    } catch {
      setError(failureMessage())
    }
    setPending(false)
    return saved
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    if (name.trim() && (await run(() => createStandardTag(name)))) {
      setName('')
    }
  }

  function handleRename(tag: Tag) {
    const next = window.prompt('Новое название тега', tag.name)
    if (next !== null && next.trim() && next.trim() !== tag.name) {
      void run(() => renameTag(tag.id, next))
    }
  }

  if (query.isPending || unauthorized) {
    return <Loader aria-label="Загрузка тегов" />
  }
  const tags = query.data?.status === 200 ? query.data.data.tags : undefined
  if (!tags) {
    return (
      <Alert color="red" title="Не удалось загрузить теги">
        <Button size="xs" variant="default" onClick={() => void query.refetch()}>
          Повторить
        </Button>
      </Alert>
    )
  }

  return (
    <Flex direction={{ base: 'column', md: 'row' }} gap="xl" align="flex-start">
      <Stack gap="lg" style={{ flex: 1, minWidth: 0 }} w="100%">
        <Title order={1}>Теги</Title>
        {error && (
          <Alert color="red" role="alert" withCloseButton onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
        <Stack gap={0} style={{ borderTop: '2px solid var(--mantine-color-ink-6)' }}>
          {tags.length === 0 && (
            <Text c="dimmed" py="md">
              Тегов пока нет.
            </Text>
          )}
          {tags.map((tag) => (
            <Group
              key={tag.id}
              justify="space-between"
              wrap="wrap"
              gap="sm"
              py="md"
              style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}
            >
              <Group gap="md" wrap="wrap" style={{ minWidth: 0 }}>
                <TagBadge tag={tag} />
                <Text size="sm" c="dimmed">
                  {tag.standard ? 'Стандартный' : tag.author}
                </Text>
                <Text size="sm" c="dimmed">
                  диалогов: {tag.conversation_count}
                </Text>
              </Group>
              <Group gap="xs" wrap="nowrap">
                <Button size="xs" variant="default" disabled={pending} onClick={() => handleRename(tag)}>
                  Переименовать
                </Button>
                <Button
                  size="xs"
                  variant="light"
                  color="red"
                  disabled={pending}
                  onClick={() => confirmTagDelete(tag) && void run(() => deleteTag(tag.id))}
                >
                  Удалить
                </Button>
              </Group>
            </Group>
          ))}
        </Stack>
      </Stack>

      <Paper bg="gray.0" p="lg" w={{ base: '100%', md: 320 }} style={{ flexShrink: 0 }}>
        <form onSubmit={handleCreate}>
          <Stack gap="md">
            <TextInput
              label="Новый стандартный тег"
              maxLength={50}
              value={name}
              onChange={(event) => setName(event.currentTarget.value)}
            />
            <Button type="submit" loading={pending} disabled={!name.trim()} fullWidth>
              Добавить
            </Button>
            <Text size="sm" c="dimmed">
              Стандартные теги видны всем менеджерам в подсказках. Менеджеры создают свои теги сами и
              удаляют только свои. Удалённый тег снимается со всех диалогов.
            </Text>
          </Stack>
        </form>
      </Paper>
    </Flex>
  )
}
