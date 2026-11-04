import {
  ActionIcon,
  Alert,
  Anchor,
  Avatar,
  Badge,
  Box,
  Button,
  CloseButton,
  FileButton,
  Flex,
  Group,
  Image,
  Loader,
  Paper,
  ScrollArea,
  Stack,
  Text,
  Textarea,
  UnstyledButton,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState, type FormEvent } from 'react'

import { failureMessage } from '@/common/api-client'
import { useSession } from '@/modules/session'
import { ConversationTags, TagBadge, tagsQueryOptions } from '@/modules/tags'

import {
  arrange,
  attachmentUrl,
  conversationsQueryOptions,
  deleteSavedFilter,
  hasFilters,
  markRead,
  NO_FILTERS,
  preferencesQueryOptions,
  saveFilter,
  saveSort,
  MAX_CAPTION_LENGTH,
  MAX_FILE_BYTES,
  MAX_TEXT_LENGTH,
  retryMessage,
  sendFile,
  sendReply,
  threadQueryOptions,
  type ConversationSummary,
  type Filters,
  type Message,
  type Preferences,
  type Result,
  type Sort,
} from '../api/inbox'
import { InboxToolbar } from './inbox-toolbar'

// Рамка во весь экран под шапкой (≈49px) и отступами страницы.
const HEIGHT = 'calc(100dvh - 90px)'

const FILTER_LABELS: Record<keyof Filters, string> = { channel: 'Канал', status: 'Статус', tag: 'Тег' }

function newMessages(count: number) {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) {
    return `${count} новое сообщение`
  }
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return `${count} новых сообщения`
  }
  return `${count} новых сообщений`
}

function initials(name: string) {
  const letters = name
    .replace(/^@/, '')
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word[0])
  return letters.slice(0, 2).join('').toUpperCase() || '?'
}

function formatTime(iso: string) {
  const date = new Date(iso)
  const time = date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  if (date.toDateString() === new Date().toDateString()) {
    return time
  }
  return `${date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })} ${time}`
}

function formatSize(bytes: number | null) {
  if (bytes === null) {
    return ''
  }
  if (bytes < 1024 * 1024) {
    return ` (${Math.max(1, Math.round(bytes / 1024))} КБ)`
  }
  return ` (${(bytes / 1024 / 1024).toFixed(1)} МБ)`
}

function preview(message: Message | null) {
  if (!message) {
    return ''
  }
  const prefix = message.direction === 'out' ? 'Вы: ' : ''
  if (message.kind === 'unsupported') {
    return `${prefix}Неподдерживаемое сообщение`
  }
  if (message.file && !message.text) {
    return `${prefix}Файл: ${message.file.name}`
  }
  return `${prefix}${message.text ?? ''}`
}

/**
 * «Входящие» (#6, #7): список диалогов с сортировкой и фильтрами и открытый диалог.
 * Порядок списка зафиксирован снимком: новые сообщения не переставляют диалоги,
 * а показывают плашку «N новых сообщений»; «Показать» берёт новый снимок.
 */
export function InboxPanel() {
  const { setSubject } = useSession()
  const queryClient = useQueryClient()
  const list = useQuery(conversationsQueryOptions)
  const preferences = useQuery(preferencesQueryOptions)
  const allTags = useQuery(tagsQueryOptions)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [filters, setFilters] = useState<Filters>(NO_FILTERS)
  const [snapshot, setSnapshot] = useState<{ ids: number[]; incoming: number } | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const data = list.data
  const unauthorized = data?.kind === 'unauthorized'
  useEffect(() => {
    if (unauthorized) {
      setSubject(null)
    }
  }, [unauthorized, setSubject])

  const value = data?.kind === 'success' ? data.value : null
  const prefs = preferences.data?.kind === 'success' ? preferences.data.value : null
  const sort = prefs?.sort ?? 'newest'
  const ids = snapshot?.ids ?? (value ? arrange(value.conversations, sort, filters) : [])
  const fresh = value && snapshot ? value.incoming_total - snapshot.incoming : 0

  // Снимок берётся, когда списка ещё нет (открытие, смена сортировки/фильтров, «Показать»).
  useEffect(() => {
    if (value && !preferences.isPending && snapshot === null) {
      setSnapshot({ ids: arrange(value.conversations, sort, filters), incoming: value.incoming_total })
    }
  }, [value, preferences.isPending, snapshot, sort, filters])

  const selected = value?.conversations.find((item) => item.id === selectedId) ?? null
  const selectedUnread = selected?.unread_count ?? 0

  // Открытый диалог прочитан, в том числе когда в нём появились новые сообщения.
  useEffect(() => {
    if (selectedId === null || selectedUnread === 0) {
      return
    }
    void markRead(selectedId)
      .then(() => queryClient.invalidateQueries({ queryKey: conversationsQueryOptions.queryKey }))
      .catch(() => undefined)
  }, [selectedId, selectedUnread, queryClient])

  function applyFilters(next: Filters) {
    setFilters(next)
    setSnapshot(null)
  }

  /** Сохраняет настройки на сервере; ответ заменяет кэш предпочтений. */
  async function savePreferences(action: () => Promise<Result<Preferences>>) {
    setNotice(null)
    try {
      const result = await action()
      if (result.kind === 'success') {
        queryClient.setQueryData(preferencesQueryOptions.queryKey, result)
      } else if (result.kind === 'unauthorized') {
        setSubject(null)
      } else {
        setNotice(result.kind === 'failed' ? failureMessage(result.status) : failureMessage(404))
      }
    } catch {
      setNotice(failureMessage())
    }
  }

  function changeSort(next: Sort) {
    if (prefs) {
      const optimistic: Result<Preferences> = { kind: 'success', value: { ...prefs, sort: next } }
      queryClient.setQueryData(preferencesQueryOptions.queryKey, optimistic)
    }
    setSnapshot(null)
    void savePreferences(() => saveSort(next))
  }

  function saveCurrent() {
    const name = window.prompt('Название набора фильтров')?.trim()
    if (name) {
      void savePreferences(() => saveFilter(name.slice(0, 50), filters))
    }
  }

  if (list.isPending || preferences.isPending || unauthorized) {
    return <Loader aria-label="Загрузка диалогов" />
  }
  if (!value) {
    return (
      <Alert color="red" title="Не удалось загрузить диалоги">
        <Stack gap="xs" align="flex-start">
          <span>{data?.kind === 'failed' ? failureMessage(data.status) : failureMessage()}</span>
          <Button size="xs" variant="default" onClick={() => void list.refetch()}>
            Повторить
          </Button>
        </Stack>
      </Alert>
    )
  }

  const byId = new Map(value.conversations.map((item) => [item.id, item]))
  const rows = ids.flatMap((id) => byId.get(id) ?? [])
  const tags = allTags.data?.status === 200 ? (allTags.data.data.tags ?? []) : []
  const active = (Object.keys(FILTER_LABELS) as (keyof Filters)[]).filter((key) => filters[key].length > 0)

  return (
    <Flex direction={{ base: 'column', md: 'row' }} gap="xl" align={{ base: 'stretch', md: 'flex-start' }}>
      <Box w={{ md: 260 }} style={{ flexShrink: 0 }}>
        <InboxToolbar
          sort={sort}
          onSort={changeSort}
          filters={filters}
          onFilters={applyFilters}
          tags={tags}
          saved={prefs?.saved_filters ?? []}
          found={rows.length}
          onApplySaved={(saved) =>
            // Удалённые с тех пор теги из набора выпадают.
            applyFilters({ ...NO_FILTERS, ...saved, tag: saved.tag.filter((id) => tags.some((tag) => tag.id === id)) })
          }
          onSaveCurrent={hasFilters(filters) ? saveCurrent : null}
          onDeleteSaved={(id) => void savePreferences(() => deleteSavedFilter(id))}
        />
      </Box>
      <Stack gap="sm" style={{ flex: 1, minWidth: 0 }}>
        {notice && (
          <Alert color="red" role="alert" withCloseButton onClose={() => setNotice(null)}>
            {notice}
          </Alert>
        )}
        <Paper withBorder style={{ display: 'flex', height: HEIGHT, overflow: 'hidden' }}>
          <Box
            w={{ base: '100%', sm: 340 }}
            display={{ base: selectedId === null ? 'flex' : 'none', sm: 'flex' }}
            style={{ flexDirection: 'column', borderRight: '1px solid var(--mantine-color-gray-3)' }}
          >
            <Group gap="sm" px="md" py="sm" bg="gray.0" style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}>
              <Text fw={600} size="sm">
                Все каналы
              </Text>
              <Text size="sm" c="dimmed">
                непрочитанных {value.unread_total}
              </Text>
            </Group>
            {fresh > 0 && (
              <UnstyledButton
                onClick={() => setSnapshot(null)}
                py={6}
                ta="center"
                c="blue"
                fz="sm"
                style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}
              >
                Показать {newMessages(fresh)}
              </UnstyledButton>
            )}
            <ScrollArea style={{ flex: 1 }}>
              {value.conversations.length === 0 && (
                <Text size="sm" c="dimmed" p="md">
                  Пока нет диалогов. Сообщения клиентов из подключённых мессенджеров появятся здесь.
                </Text>
              )}
              {value.conversations.length > 0 && rows.length === 0 && active.length > 0 && (
                <Stack gap="xs" p="md" align="flex-start">
                  <Text size="sm">По этим фильтрам ничего не найдено.</Text>
                  <Group gap="xs">
                    {active.map((key) => (
                      <Button key={key} size="compact-xs" variant="default" onClick={() => applyFilters({ ...filters, [key]: [] })}>
                        Сбросить «{FILTER_LABELS[key]}»
                      </Button>
                    ))}
                  </Group>
                  <Button size="xs" onClick={() => applyFilters(NO_FILTERS)}>
                    Сбросить все фильтры
                  </Button>
                </Stack>
              )}
              {rows.map((item) => (
                <ConversationRow
                  key={item.id}
                  item={item}
                  active={item.id === selectedId}
                  onSelect={() => setSelectedId(item.id)}
                />
              ))}
            </ScrollArea>
          </Box>

          <Box
            style={{ flex: 1, minWidth: 0, flexDirection: 'column' }}
            display={{ base: selectedId === null ? 'none' : 'flex', sm: 'flex' }}
          >
            {selectedId === null ? (
              <Text c="dimmed" m="auto" p="md">
                Выберите диалог
              </Text>
            ) : (
              <ThreadView key={selectedId} id={selectedId} onClose={() => setSelectedId(null)} />
            )}
          </Box>
        </Paper>
      </Stack>
    </Flex>
  )
}

function ConversationRow({
  item,
  active,
  onSelect,
}: {
  item: ConversationSummary
  active: boolean
  onSelect: () => void
}) {
  return (
    <UnstyledButton
      onClick={onSelect}
      w="100%"
      px="md"
      py="sm"
      bg={active ? 'gray.1' : undefined}
      aria-current={active || undefined}
      style={{
        borderBottom: '1px solid var(--mantine-color-gray-2)',
        boxShadow: active ? 'inset 3px 0 0 var(--mantine-color-ink-6)' : undefined,
        display: 'block',
      }}
    >
      <Group gap="sm" wrap="nowrap" align="flex-start">
        <Avatar radius="xl" color="initials" name={item.name}>
          {initials(item.name)}
        </Avatar>
        <Box style={{ flex: 1, minWidth: 0 }}>
          <Group justify="space-between" wrap="nowrap" gap="xs">
            <Group gap={6} wrap="nowrap" style={{ minWidth: 0 }}>
              <Text size="sm" fw={600} truncate>
                {item.name}
              </Text>
              <Badge size="xs" variant="outline" color="gray">
                TG
              </Badge>
            </Group>
            <Text size="xs" c="dimmed" style={{ flexShrink: 0 }}>
              {formatTime(item.last_message_at)}
            </Text>
          </Group>
          <Group justify="space-between" wrap="nowrap" gap="xs">
            <Text size="sm" c="dimmed" truncate>
              {preview(item.last_message)}
            </Text>
            {item.unread_count > 0 && (
              <Badge size="sm" color="red" circle={item.unread_count < 10} aria-label={`непрочитанных: ${item.unread_count}`}>
                {item.unread_count}
              </Badge>
            )}
          </Group>
          {item.tags.length > 0 && (
            <Group gap={4} mt={4}>
              {item.tags.map((tag) => (
                <TagBadge key={tag.id} tag={tag} />
              ))}
            </Group>
          )}
        </Box>
      </Group>
    </UnstyledButton>
  )
}

function ThreadView({ id, onClose }: { id: number; onClose: () => void }) {
  const { setSubject } = useSession()
  const queryClient = useQueryClient()
  const query = useQuery(threadQueryOptions(id))
  const viewport = useRef<HTMLDivElement>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const data = query.data
  const thread = data?.kind === 'success' ? data.value : null
  const count = thread?.messages.length ?? 0

  useEffect(() => {
    if (data?.kind === 'unauthorized') {
      setSubject(null)
    }
  }, [data, setSubject])

  useEffect(() => {
    viewport.current?.scrollTo({ top: viewport.current.scrollHeight })
  }, [count])

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: conversationsQueryOptions.queryKey })
  }

  /** Обрабатывает ответ отправки; `true` — сообщение сохранено на сервере. */
  function handle(result: Result<Message>) {
    if (result.kind === 'success') {
      refresh()
      return true
    }
    if (result.kind === 'unauthorized') {
      setSubject(null)
    } else {
      setNotice(result.kind === 'not-found' ? 'Диалог не найден.' : failureMessage(result.status))
    }
    return false
  }

  async function handleRetry(message: Message) {
    if (!window.confirm('Сообщение могло дойти до клиента. Отправить ещё раз? Возможен дубль.')) {
      return
    }
    setNotice(null)
    try {
      const result = await retryMessage(message.id)
      if (result.kind === 'failed' && result.status === 409) {
        refresh()
        return
      }
      handle(result)
    } catch {
      setNotice(failureMessage())
    }
  }

  if (query.isPending) {
    return <Loader m="auto" aria-label="Загрузка диалога" />
  }
  if (!thread) {
    return (
      <Alert color="red" m="md" title="Не удалось открыть диалог">
        <Group gap="xs">
          <Button size="xs" variant="default" onClick={() => void query.refetch()}>
            Повторить
          </Button>
          <Button size="xs" variant="subtle" onClick={onClose}>
            К списку
          </Button>
        </Group>
      </Alert>
    )
  }

  return (
    <>
      <Group
        gap="sm"
        px="md"
        py="sm"
        wrap="nowrap"
        style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}
      >
        <CloseButton hiddenFrom="sm" aria-label="К списку диалогов" onClick={onClose} />
        <Avatar radius="xl" color="initials" name={thread.conversation.name}>
          {initials(thread.conversation.name)}
        </Avatar>
        <Text fw={600} truncate>
          {thread.conversation.name}
        </Text>
        <Badge variant="outline" color="gray" size="sm">
          Telegram
        </Badge>
      </Group>
      <ConversationTags conversationId={id} tags={thread.conversation.tags} />

      <ScrollArea style={{ flex: 1 }} viewportRef={viewport} px="md">
        <Stack gap="sm" py="md">
          {thread.messages.map((message) => (
            <MessageBubble key={message.id} message={message} onRetry={() => void handleRetry(message)} />
          ))}
        </Stack>
      </ScrollArea>

      {notice && (
        <Alert color="red" role="alert" mx="md" withCloseButton onClose={() => setNotice(null)}>
          {notice}
        </Alert>
      )}
      <Composer
        onSend={async (text, file) => {
          setNotice(null)
          try {
            return handle(file ? await sendFile(id, file, text) : await sendReply(id, text))
          } catch {
            setNotice(failureMessage())
            return false
          }
        }}
      />
    </>
  )
}

function MessageBubble({ message, onRetry }: { message: Message; onRetry: () => void }) {
  const out = message.direction === 'out'
  const file = message.file
  return (
    <Paper
      px="md"
      py="sm"
      maw="75%"
      bg={out ? 'blue.0' : 'gray.0'}
      style={{
        alignSelf: out ? 'flex-end' : 'flex-start',
        // «Хвостик» пузыря — острый угол со стороны автора.
        borderRadius: out ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
      }}
    >
      <Stack gap={6}>
        {message.kind === 'unsupported' && (
          <Text size="sm" fs="italic" c="dimmed">
            Неподдерживаемое сообщение
          </Text>
        )}
        {file && message.kind === 'photo' && file.available && (
          <Group gap="sm" align="flex-end">
            <Image src={attachmentUrl(message.id)} alt={file.name} h={160} w="auto" fit="contain" radius="md" />
            <Anchor href={attachmentUrl(message.id)} target="_blank" rel="noopener" size="sm">
              открыть
            </Anchor>
          </Group>
        )}
        {file && message.kind !== 'photo' && file.available && (
          <Group gap="sm" wrap="wrap">
            <Text size="sm" style={{ overflowWrap: 'anywhere' }}>
              {file.name}
              {formatSize(file.size)}
            </Text>
            <Anchor href={attachmentUrl(message.id)} download={file.name} size="sm">
              открыть
            </Anchor>
          </Group>
        )}
        {file && !file.available && (
          <Text size="sm" c="dimmed" style={{ overflowWrap: 'anywhere' }}>
            {file.name}: файл недоступен (больше 20 МБ или не скачался)
          </Text>
        )}
        {message.text && (
          <Text size="sm" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
            {message.text}
          </Text>
        )}
        <Group gap={6}>
          <Text size="xs" c="dimmed">
            {formatTime(message.created_at)}
          </Text>
          {message.status === 'delivered' && (
            <Text size="xs" c="dimmed">
              ✓✓ доставлено
            </Text>
          )}
          {message.status === 'sending' && (
            <Text size="xs" c="dimmed">
              отправляется…
            </Text>
          )}
          {message.status === 'failed' && (
            <>
              <Text size="xs" c="red" fw={600}>
                Не доставлено
              </Text>
              <Anchor component="button" size="xs" onClick={onRetry}>
                Повторить
              </Anchor>
            </>
          )}
        </Group>
      </Stack>
    </Paper>
  )
}

function Composer({ onSend }: { onSend: (text: string, file: File | null) => Promise<boolean> }) {
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [pending, setPending] = useState(false)

  const limit = file ? MAX_CAPTION_LENGTH : MAX_TEXT_LENGTH
  const tooBig = file !== null && file.size > MAX_FILE_BYTES
  const error = tooBig
    ? 'Файл больше 20 МБ'
    : text.length > limit
      ? `Не больше ${limit} символов${file ? ' вместе с файлом' : ''}`
      : null
  const canSend = (text.trim() !== '' || file !== null) && !error && !pending

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!canSend) {
      return
    }
    setPending(true)
    // Текст и файл очищаются, только когда ответ сохранён на сервере; при
    // «Не доставлено» текст остаётся в сообщении и его можно отправить повторно.
    if (await onSend(text.trim(), file)) {
      setText('')
      setFile(null)
    }
    setPending(false)
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <Stack gap={4} p="md" style={{ borderTop: '1px solid var(--mantine-color-gray-3)' }}>
        {file && (
          <Group gap={4}>
            <Text size="sm" style={{ overflowWrap: 'anywhere' }}>
              Файл: {file.name}
              {formatSize(file.size)}
            </Text>
            <CloseButton size="sm" aria-label="Убрать файл" onClick={() => setFile(null)} />
          </Group>
        )}
        <Group gap="sm" wrap="nowrap" align="flex-end">
          <Textarea
            aria-label="Ответ"
            placeholder="Ответ… (уйдёт в Telegram)"
            autosize
            minRows={1}
            maxRows={6}
            style={{ flex: 1 }}
            value={text}
            error={error}
            onChange={(event) => setText(event.currentTarget.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                void handleSubmit(event)
              }
            }}
          />
          <FileButton onChange={setFile}>
            {(props) => (
              <ActionIcon {...props} variant="default" size="lg" aria-label="Прикрепить файл">
                {/* скрепка, путь из Tabler Icons (MIT) */}
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M15 7l-6.5 6.5a1.5 1.5 0 0 0 3 3l6.5 -6.5a3 3 0 0 0 -6 -6l-6.5 6.5a4.5 4.5 0 0 0 9 9l6.5 -6.5" />
                </svg>
              </ActionIcon>
            )}
          </FileButton>
          <Button type="submit" loading={pending} disabled={!canSend}>
            Отправить
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
