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

import {
  attachmentUrl,
  conversationsQueryOptions,
  markRead,
  MAX_CAPTION_LENGTH,
  MAX_FILE_BYTES,
  MAX_TEXT_LENGTH,
  retryMessage,
  sendFile,
  sendReply,
  threadQueryOptions,
  type ConversationSummary,
  type Message,
  type Result,
} from '../api/inbox'

const HEIGHT = 'calc(100dvh - 140px)'

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
    return ` · ${Math.max(1, Math.round(bytes / 1024))} КБ`
  }
  return ` · ${(bytes / 1024 / 1024).toFixed(1)} МБ`
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
    return `${prefix}📎 ${message.file.name}`
  }
  return `${prefix}${message.text ?? ''}`
}

/** «Входящие» (#6): единый список диалогов и открытый диалог с ответом. */
export function InboxPanel() {
  const { setSubject } = useSession()
  const queryClient = useQueryClient()
  const list = useQuery(conversationsQueryOptions)
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const data = list.data
  const unauthorized = data?.kind === 'unauthorized'
  useEffect(() => {
    if (unauthorized) {
      setSubject(null)
    }
  }, [unauthorized, setSubject])

  const value = data?.kind === 'success' ? data.value : null
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

  if (list.isPending || unauthorized) {
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

  return (
    <Paper withBorder radius="md" style={{ display: 'flex', height: HEIGHT, overflow: 'hidden' }}>
      <Box
        w={{ base: '100%', sm: 340 }}
        display={{ base: selectedId === null ? 'flex' : 'none', sm: 'flex' }}
        style={{ flexDirection: 'column', borderRight: '1px solid var(--mantine-color-gray-3)' }}
      >
        <Group gap={6} px="md" py="sm" style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}>
          <Text fw={600} size="sm">
            Все каналы
          </Text>
          <Text size="sm" c="dimmed">
            · непрочитанных {value.unread_total}
          </Text>
        </Group>
        <ScrollArea style={{ flex: 1 }}>
          {value.conversations.length === 0 && (
            <Text size="sm" c="dimmed" p="md">
              Пока нет диалогов. Сообщения клиентов из подключённых мессенджеров появятся здесь.
            </Text>
          )}
          {value.conversations.map((item) => (
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
      bg={active ? 'blue.0' : undefined}
      aria-current={active || undefined}
      style={{ borderBottom: '1px solid var(--mantine-color-gray-2)', display: 'block' }}
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
              <Badge size="sm" circle={item.unread_count < 10} aria-label={`непрочитанных: ${item.unread_count}`}>
                {item.unread_count}
              </Badge>
            )}
          </Group>
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
      withBorder
      p="sm"
      radius="md"
      maw="75%"
      bg={out ? 'blue.0' : 'white'}
      style={{ alignSelf: out ? 'flex-end' : 'flex-start' }}
    >
      <Stack gap={6}>
        {message.kind === 'unsupported' && (
          <Text size="sm" fs="italic" c="dimmed">
            Неподдерживаемое сообщение
          </Text>
        )}
        {file && message.kind === 'photo' && file.available && (
          <Group gap="sm" align="flex-end">
            <Image src={attachmentUrl(message.id)} alt={file.name} h={160} w="auto" fit="contain" radius="sm" />
            <Anchor href={attachmentUrl(message.id)} target="_blank" rel="noopener" size="sm">
              открыть
            </Anchor>
          </Group>
        )}
        {file && message.kind !== 'photo' && file.available && (
          <Text size="sm" style={{ overflowWrap: 'anywhere' }}>
            📄 {file.name}
            {formatSize(file.size)} ·{' '}
            <Anchor href={attachmentUrl(message.id)} download={file.name} size="sm">
              открыть
            </Anchor>
          </Text>
        )}
        {file && !file.available && (
          <Text size="sm" c="dimmed" style={{ overflowWrap: 'anywhere' }}>
            📎 {file.name} — файл недоступен (больше 20 МБ или не скачался)
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
              · ✓✓ доставлено
            </Text>
          )}
          {message.status === 'sending' && (
            <Text size="xs" c="dimmed">
              · отправляется…
            </Text>
          )}
          {message.status === 'failed' && (
            <>
              <Text size="xs" c="red" fw={600}>
                · Не доставлено
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
              📎 {file.name}
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
                📎
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
