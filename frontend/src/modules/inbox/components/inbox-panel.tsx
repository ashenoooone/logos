import { TELEGRAM_LABEL } from '@/common/channel-label'
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
  Menu,
  Paper,
  ScrollArea,
  Skeleton,
  Stack,
  Tabs,
  Text,
  TextInput,
  Textarea,
  Tooltip,
  UnstyledButton,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState, type FormEvent } from 'react'

import { failureMessage } from '@/common/api-client'
import { ClientNotes } from '@/modules/notes'
import { useSession } from '@/modules/session'
import { ConversationTags, TagBadge, tagsQueryOptions } from '@/modules/tags'
import { ReplyTemplates } from '@/modules/templates'

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
  PIN_LIMIT,
  pinConversation,
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
  unpinConversation,
} from '../api/inbox'
import { InboxToolbar } from './inbox-toolbar'
import { ThreadComments } from './thread-comments'

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
  const prefix = message.direction === 'out' ? `${message.author ?? 'Менеджер'}: ` : ''
  if (message.kind === 'unsupported') {
    return `${prefix}Неподдерживаемое сообщение`
  }
  if (message.file && !message.text) {
    return `${prefix}Файл: ${message.file.name}`
  }
  return `${prefix}${message.text ?? ''}`
}

/** Булавка (#12); путь из Tabler Icons (MIT). */
function PinIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M15 4.5l-4 4l-4 1.5l-1.5 1.5l7 7l1.5 -1.5l1.5 -4l4 -4" />
      <path d="M9 15l-4.5 4.5" />
      <path d="M14.5 4l5.5 5.5" />
    </svg>
  )
}

function DotsIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <circle cx="12" cy="5" r="2" />
      <circle cx="12" cy="12" r="2" />
      <circle cx="12" cy="19" r="2" />
    </svg>
  )
}

/** Свежие закрепления сверху; порядок не зависит от новых сообщений. */
function byPinTime(a: ConversationSummary, b: ConversationSummary) {
  return Date.parse(b.pinned_at ?? '') - Date.parse(a.pinned_at ?? '') || b.id - a.id
}

/**
 * «Входящие» (#6, #7): список диалогов с сортировкой и фильтрами и открытый диалог.
 * Порядок списка зафиксирован снимком: новые сообщения не переставляют диалоги,
 * а показывают плашку «N новых сообщений»; «Показать» берёт новый снимок.
 */
export function InboxPanel() {
  const { setSubject } = useSession()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const list = useQuery(conversationsQueryOptions(search))
  const preferences = useQuery(preferencesQueryOptions)
  const allTags = useQuery(tagsQueryOptions)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [filters, setFilters] = useState<Filters>(NO_FILTERS)
  const [snapshot, setSnapshot] = useState<{ ids: number[]; incoming: number; query: string } | null>(null)
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
  const currentSnapshot = snapshot?.query === search ? snapshot : null
  const fresh = value && currentSnapshot ? Math.max(0, value.incoming_total - currentSnapshot.incoming) : 0
  // Только первая загрузка запроса; фоновый опрос и фильтры (на клиенте) без индикатора.
  const listPending = list.isPending
  const listFailed = data?.kind === 'failed'

  // Query changes get a new snapshot; existing order remains frozen within that query.
  useEffect(() => {
    if (value && !preferences.isPending && currentSnapshot === null) {
      setSnapshot({ ids: arrange(value.conversations, sort, filters), incoming: value.incoming_total, query: search })
    }
  }, [value, preferences.isPending, currentSnapshot, sort, filters, search])

  const thread = useQuery({
    ...threadQueryOptions(selectedId ?? 0),
    enabled: selectedId !== null,
  })
  const readMessageId = thread.data?.kind === 'success'
    ? [...thread.data.value.messages].reverse().find((message) => message.direction === 'in')?.id ?? null
    : null
  const markedRead = useRef<number | null>(null)
  const markingRead = useRef<number | null>(null)
  useEffect(() => {
    if (selectedId === null || readMessageId === null || markedRead.current === readMessageId || markingRead.current === readMessageId) return
    markingRead.current = readMessageId
    void markRead(selectedId)
      .then(() => {
        markedRead.current = readMessageId
        return queryClient.invalidateQueries({ queryKey: ['conversations'] })
      })
      .catch(() => {})
      .finally(() => {
        if (markingRead.current === readMessageId) markingRead.current = null
      })
  }, [selectedId, readMessageId, queryClient])

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

  /** Закрепляет или снимает закрепление (#12); лимит проверяет и сервер. */
  async function togglePin(item: ConversationSummary) {
    setNotice(null)
    try {
      const result = item.pinned_at
        ? await unpinConversation(item.id)
        : await pinConversation(item.id)
      if (result.kind === 'unauthorized') {
        setSubject(null)
        return
      }
      if (result.kind === 'failed') {
        setNotice(
          result.status === 409
            ? `Закреплено ${PIN_LIMIT} из ${PIN_LIMIT}. Снимите закрепление с одного из диалогов.`
            : failureMessage(result.status),
        )
        return
      }
      if (result.kind === 'not-found') {
        setNotice('Диалог не найден.')
        return
      }
      setSnapshot(null)
      await queryClient.invalidateQueries({ queryKey: ['conversations'] })
    } catch {
      setNotice(failureMessage())
    }
  }

  const byId = new Map((value?.conversations ?? []).map((item) => [item.id, item]))
  const ids = currentSnapshot?.ids ?? (value ? arrange(value.conversations, sort, filters) : [])
  const pinned = (value?.conversations ?? []).filter((item) => item.pinned_at !== null).sort(byPinTime)
  const rows = ids
    .map((id) => byId.get(id))
    .filter((item): item is ConversationSummary => item !== undefined && item.pinned_at === null)
  const pinLimitReached = pinned.length >= PIN_LIMIT
  const tags = allTags.data?.status === 200 ? (allTags.data.data.tags ?? []) : []
  const active = (Object.keys(FILTER_LABELS) as (keyof Filters)[]).filter((key) => filters[key].length > 0)

  if (preferences.isPending || unauthorized) {
    return <Loader aria-label="Загрузка диалогов" />
  }
  

  return (
    <Flex direction={{ base: 'column', md: 'row' }} gap="xl" align={{ base: 'stretch', md: 'flex-start' }}>
      <Box w={{ md: 260 }} style={{ flexShrink: 0 }}>
        <TextInput
          aria-label="Поиск по сообщениям"
          placeholder="Поиск по переписке"
          value={search}
          onChange={(event) => setSearch(event.currentTarget.value)}
          rightSection={search ? <CloseButton aria-label="Очистить поиск" onClick={() => setSearch('')} /> : null}
          rightSectionPointerEvents={search ? 'auto' : 'none'}
          mb="sm"
        />
        <InboxToolbar
          sort={sort}
          onSort={changeSort}
          filters={filters}
          onFilters={applyFilters}
          tags={tags}
          saved={prefs?.saved_filters ?? []}
          found={rows.length + pinned.length}
          onApplySaved={(saved) =>
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
              <Text fw={600} size="sm">Все каналы</Text>
              {value && <Text size="sm" c="dimmed">непрочитанных {value.unread_total}</Text>}
            </Group>
            {fresh > 0 && (
              <UnstyledButton onClick={() => setSnapshot(null)} py={6} ta="center" c="blue" fz="sm">
                Показать {newMessages(fresh)}
              </UnstyledButton>
            )}
            <ScrollArea style={{ flex: 1 }}>
              {pinned.length > 0 && (
                <Box style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}>
                  <Group gap={6} px="md" py={6} bg="gray.0">
                    <Box c="dimmed" style={{ display: 'flex' }}>
                      <PinIcon />
                    </Box>
                    <Text size="sm" fw={600}>
                      Закреплённые
                    </Text>
                    <Text size="xs" c="dimmed" ml="auto">
                      {pinned.length} из {PIN_LIMIT}
                    </Text>
                  </Group>
                  {pinned.map((item) => (
                    <ConversationRow
                      key={item.id}
                      item={item}
                      active={item.id === selectedId}
                      onSelect={() => setSelectedId(item.id)}
                      onTogglePin={() => void togglePin(item)}
                      pinLimitReached={pinLimitReached}
                    />
                  ))}
                </Box>
              )}
              {listFailed || list.isError ? (
                <Alert color="red" role="alert" m="md" title="Не удалось загрузить диалоги">
                  <Group justify="space-between" align="center">
                    <Text size="sm">{listFailed ? failureMessage(data.status) : failureMessage()}</Text>
                    <Button size="xs" variant="light" onClick={() => void list.refetch()}>Повторить</Button>
                  </Group>
                </Alert>
              ) : null}
              {value && !listPending && value.conversations.length === 0 && !search && (
                <Text size="sm" c="dimmed" p="md">
                  Пока нет диалогов. Сообщения клиентов из подключённых мессенджеров появятся здесь.
                </Text>
              )}
              {value && !listPending && rows.length === 0 && pinned.length === 0 && (active.length > 0 || search) && (
                <Stack gap="xs" p="md" align="flex-start">
                  <Text size="sm">{search ? 'По запросу ничего не найдено.' : 'По этим фильтрам ничего не найдено.'}</Text>
                  {active.length > 0 && (
                    <Group gap="xs">
                      {active.map((key) => (
                        <Button key={key} size="compact-xs" variant="default" onClick={() => applyFilters({ ...filters, [key]: [] })}>
                          Сбросить «{FILTER_LABELS[key]}»
                        </Button>
                      ))}
                    </Group>
                  )}
                  {active.length > 0 && (
                    <Button size="xs" onClick={() => applyFilters(NO_FILTERS)}>
                      Сбросить все фильтры
                    </Button>
                  )}
                  {search && <Button size="xs" variant="default" onClick={() => setSearch('')}>Очистить поиск</Button>}
                </Stack>
              )}
              {listPending && !listFailed && (
                <Box aria-busy aria-label="Поиск диалогов">
                  {[0, 1, 2, 3, 4, 5].map((index) => (
                    <ConversationRowSkeleton key={index} />
                  ))}
                </Box>
              )}
              {rows.map((item) => (
                <ConversationRow
                  key={item.id}
                  item={item}
                  active={item.id === selectedId}
                  onSelect={() => setSelectedId(item.id)}
                  onTogglePin={() => void togglePin(item)}
                  pinLimitReached={pinLimitReached}
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
              <ThreadView
                key={selectedId}
                id={selectedId}
                onClose={() => setSelectedId(null)}
                pinnedAt={byId.get(selectedId)?.pinned_at ?? null}
                pinCount={pinned.length}
                onTogglePin={() => {
                  const item = byId.get(selectedId)
                  if (item) {
                    void togglePin(item)
                  }
                }}
              />
            )}
          </Box>
        </Paper>
      </Stack>
    </Flex>
  )
}


/** Повторяет разметку ConversationRow: аватар, имя + канал + время, превью. */
function ConversationRowSkeleton() {
  return (
    <Box px="md" py="sm" style={{ borderBottom: '1px solid var(--mantine-color-gray-2)' }}>
      <Group gap="sm" wrap="nowrap" align="flex-start">
        <Skeleton circle height={38} style={{ flexShrink: 0 }} />
        <Box style={{ flex: 1, minWidth: 0 }}>
          <Group justify="space-between" wrap="nowrap" gap="xs" h={22}>
            <Group gap={6} wrap="nowrap">
              <Skeleton height={12} width={120} radius="xl" />
              <Skeleton height={14} width={56} radius="xl" />
            </Group>
            <Skeleton height={10} width={64} radius="xl" />
          </Group>
          <Group h={22} align="center">
            <Skeleton height={10} width="80%" radius="xl" />
          </Group>
        </Box>
      </Group>
    </Box>
  )
}

function ConversationRow({
  item,
  active,
  onSelect,
  onTogglePin,
  pinLimitReached,
}: {
  item: ConversationSummary
  active: boolean
  onSelect: () => void
  onTogglePin: () => void
  pinLimitReached: boolean
}) {
  return (
    <Group
      gap={4}
      wrap="nowrap"
      px="md"
      py="sm"
      bg={active ? 'gray.1' : undefined}
      style={{
        borderBottom: '1px solid var(--mantine-color-gray-2)',
        boxShadow: active ? 'inset 3px 0 0 var(--mantine-color-ink-6)' : undefined,
      }}
    >
      <UnstyledButton
        onClick={onSelect}
        aria-current={active || undefined}
        style={{ flex: 1, minWidth: 0, display: 'block' }}
      >
        <Group gap="sm" wrap="nowrap" align="flex-start">
          <Avatar radius="xl" color="initials" name={item.name}>
            {initials(item.name)}
          </Avatar>
          <Box style={{ flex: 1, minWidth: 0 }}>
            <Group justify="space-between" wrap="nowrap" gap="xs">
              <Group gap={6} wrap="nowrap" style={{ minWidth: 0 }}>
                {item.pinned_at && (
                  <Box c="dimmed" style={{ display: 'flex', flexShrink: 0 }}>
                    <PinIcon size={13} />
                  </Box>
                )}
                <Text size="sm" fw={600} truncate>
                  {item.name}
                </Text>
                <Badge size="xs" variant="outline" color="gray">
                  {TELEGRAM_LABEL}
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
      <Menu position="bottom-end" withinPortal>
        <Menu.Target>
          <ActionIcon variant="subtle" color="gray" aria-label={`Действия с диалогом ${item.name}`}>
            <DotsIcon />
          </ActionIcon>
        </Menu.Target>
        <Menu.Dropdown>
          {item.pinned_at ? (
            <Menu.Item onClick={onTogglePin}>Открепить</Menu.Item>
          ) : (
            <Menu.Item
              onClick={onTogglePin}
              disabled={pinLimitReached}
              title={
                pinLimitReached
                  ? `Закреплено ${PIN_LIMIT} из ${PIN_LIMIT} — снимите одно из закреплённых`
                  : undefined
              }
            >
              Закрепить
            </Menu.Item>
          )}
        </Menu.Dropdown>
      </Menu>
    </Group>
  )
}

function ThreadView({
  id,
  onClose,
  pinnedAt,
  pinCount,
  onTogglePin,
}: {
  id: number
  onClose: () => void
  pinnedAt: string | null
  pinCount: number
  onTogglePin: () => void
}) {
  const { setSubject } = useSession()
  const queryClient = useQueryClient()
  const query = useQuery(threadQueryOptions(id))
  const viewport = useRef<HTMLDivElement>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [tab, setTab] = useState<'thread' | 'notes' | 'team'>('thread')

  const data = query.data
  const thread = data?.kind === 'success' ? data.value : null
  const count = thread?.messages.length ?? 0
  const pinLimitReached = pinnedAt === null && pinCount >= PIN_LIMIT

  useEffect(() => {
    if (data?.kind === 'unauthorized') {
      setSubject(null)
    }
  }, [data, setSubject])

  useEffect(() => {
    viewport.current?.scrollTo({ top: viewport.current.scrollHeight })
  }, [count])

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ['conversations'] })
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
          {TELEGRAM_LABEL}
        </Badge>
        <Box ml="auto">
          <Tooltip
            label={`Закреплено ${PIN_LIMIT} из ${PIN_LIMIT}. Снимите закрепление с одного из диалогов.`}
            disabled={!pinLimitReached}
          >
            <Button
              size="compact-sm"
              variant={pinnedAt ? 'light' : 'default'}
              leftSection={<PinIcon />}
              onClick={onTogglePin}
              disabled={pinLimitReached}
            >
              {pinnedAt ? 'Открепить' : 'Закрепить'}
            </Button>
          </Tooltip>
        </Box>
      </Group>
      <Tabs
        value={tab}
        onChange={(value) =>
          setTab(value === 'notes' ? 'notes' : value === 'team' ? 'team' : 'thread')
        }
      >
        <Tabs.List px="md">
          <Tabs.Tab value="thread">Переписка</Tabs.Tab>
          <Tabs.Tab value="notes">Заметки</Tabs.Tab>
          <Tabs.Tab value="team">Команда</Tabs.Tab>
        </Tabs.List>
      </Tabs>

      {/* Оба треда остаются смонтированными: черновики сохраняются при переключении. */}
      <Box
        style={{ flex: 1, minHeight: 0, flexDirection: 'column' }}
        display={tab === 'thread' ? 'flex' : 'none'}
      >
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
          conversationName={thread.conversation.name}
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
      </Box>

      {tab === 'notes' && <ClientNotes conversationId={id} />}

      <Box
        style={{ flex: 1, minHeight: 0, flexDirection: 'column' }}
        display={tab === 'team' ? 'flex' : 'none'}
      >
        <ThreadComments id={id} active={tab === 'team'} />
      </Box>
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
      <Stack gap={4}>
        <Text size="xs" c="dimmed">
          {message.author ?? (out ? 'Менеджер' : 'Клиент')}
        </Text>
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

function Composer({
  conversationName,
  onSend,
}: {
  conversationName: string
  onSend: (text: string, file: File | null) => Promise<boolean>
}) {
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
            placeholder={`Ответ… (уйдёт в ${TELEGRAM_LABEL})`}
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
          <ReplyTemplates
            conversationName={conversationName}
            onInsert={(template) =>
              setText((current) => (current.trim() ? `${current.trimEnd()}\n${template}` : template))
            }
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
