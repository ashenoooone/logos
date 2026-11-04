import {
  Alert,
  Anchor,
  Badge,
  Button,
  Group,
  List,
  Loader,
  Paper,
  PasswordInput,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'

import { failureMessage } from '@/common/api-client'
import { useSession } from '@/modules/session'

import {
  channelQueryOptions,
  checkToken,
  connectChannel,
  disconnectChannel,
  type Channel,
  type Result,
} from '../api/channels'

const ERRORS: Record<NonNullable<Channel['error']>, string> = {
  token_invalid: 'Токен недействителен — новые сообщения не приходят.',
  conflict: 'Бот подключён к другому приложению — новые сообщения не приходят.',
}

function message(result: Exclude<Result<unknown>, { kind: 'success' | 'unauthorized' }>) {
  switch (result.kind) {
    case 'invalid-token':
      return 'Неверный токен. Проверьте, что скопировали его из @BotFather целиком.'
    case 'already-connected':
      return 'Канал уже подключён. Обновите страницу.'
    case 'unavailable':
      return 'Telegram недоступен. Повторите попытку позже.'
    case 'failed':
      return failureMessage(result.status)
  }
}

/** Раздел «Каналы»: один Telegram-бот, подключение по токену, статус, отключение. */
export function ChannelsPanel() {
  const { setSubject } = useSession()
  const queryClient = useQueryClient()
  const query = useQuery(channelQueryOptions)
  const [formOpen, setFormOpen] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [disconnecting, setDisconnecting] = useState(false)

  const unauthorized = query.data?.kind === 'unauthorized'
  useEffect(() => {
    if (unauthorized) {
      setSubject(null) // сессия истекла — guard уведёт на вход
    }
  }, [unauthorized, setSubject])

  function store(channel: Channel) {
    const next: Result<Channel> = { kind: 'success', value: channel }
    queryClient.setQueryData(channelQueryOptions.queryKey, next)
  }

  async function handleDisconnect() {
    if (!window.confirm('Отключить канал? Новые сообщения перестанут приходить.')) {
      return
    }
    setDisconnecting(true)
    setNotice(null)
    try {
      const result = await disconnectChannel()
      if (result.kind === 'success') {
        store(result.value)
      } else if (result.kind === 'unauthorized') {
        setSubject(null)
      } else {
        setNotice(message(result))
      }
    } catch {
      setNotice(failureMessage())
    }
    setDisconnecting(false)
  }

  const data = query.data
  const channel = data?.kind === 'success' ? data.value : null

  return (
    <Stack gap="lg">
      <Group gap="xs" align="baseline">
        <Title order={1} fz={{ base: 24, sm: 28 }}>
          Каналы
        </Title>
        {channel && (
          <Text size="sm" c="dimmed">
            работает {channel.status === 'connected' ? 1 : 0} из 1
          </Text>
        )}
      </Group>

      {notice && (
        <Alert color="red" role="alert" withCloseButton onClose={() => setNotice(null)}>
          {notice}
        </Alert>
      )}

      {(query.isPending || unauthorized) && <Loader aria-label="Загрузка каналов" />}
      {(query.isError || (data && !channel && !unauthorized)) && (
        <Alert color="red" title="Не удалось загрузить каналы">
          <Stack gap="xs" align="flex-start">
            <span>{data && data.kind === 'failed' ? failureMessage(data.status) : failureMessage()}</span>
            <Button size="xs" variant="default" onClick={() => void query.refetch()}>
              Повторить
            </Button>
          </Stack>
        </Alert>
      )}

      {channel && (
        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg">
          <ChannelCard
            channel={channel}
            disconnecting={disconnecting}
            onConnect={() => setFormOpen(true)}
            onDisconnect={handleDisconnect}
          />
          {formOpen && channel.status !== 'connected' && (
            <ConnectForm
              defaultName={channel.name ?? ''}
              onCancel={() => setFormOpen(false)}
              onConnected={(value) => {
                store(value)
                setFormOpen(false)
              }}
            />
          )}
        </SimpleGrid>
      )}

      <Text size="xs" c="dimmed">
        Каналами управляет только администратор. После отключения переписка остаётся.
      </Text>
    </Stack>
  )
}

function ChannelCard({
  channel,
  disconnecting,
  onConnect,
  onDisconnect,
}: {
  channel: Channel
  disconnecting: boolean
  onConnect: () => void
  onDisconnect: () => void
}) {
  const isError = channel.status === 'error'
  return (
    <Paper
      withBorder
      radius="md"
      p={{ base: 'md', sm: 'lg' }}
      bg={isError ? 'red.0' : 'white'}
      style={isError ? { borderColor: 'var(--mantine-color-red-6)' } : undefined}
    >
      <Stack gap="sm">
        <Group justify="space-between" wrap="nowrap">
          <Title order={2} fz="lg">
            Telegram
          </Title>
          {channel.status === 'connected' && (
            <Badge color="green" variant="light">
              подключён
            </Badge>
          )}
          {isError && (
            <Badge color="red" variant="light">
              ошибка
            </Badge>
          )}
          {channel.status === 'disconnected' && (
            <Badge color="gray" variant="light">
              не подключён
            </Badge>
          )}
        </Group>

        {channel.bot_username && (
          <Text size="sm" c="dimmed" style={{ overflowWrap: 'anywhere' }}>
            {channel.name} · @{channel.bot_username}
          </Text>
        )}
        {isError && channel.error && <Text size="sm">{ERRORS[channel.error]}</Text>}

        <Group>
          {channel.status === 'connected' && (
            <Anchor component="button" size="sm" onClick={onDisconnect} disabled={disconnecting}>
              Отключить
            </Anchor>
          )}
          {isError && <Button onClick={onConnect}>Переподключить</Button>}
          {channel.status === 'disconnected' && (
            <Button variant="default" onClick={onConnect}>
              Подключить
            </Button>
          )}
        </Group>
      </Stack>
    </Paper>
  )
}

function ConnectForm({
  defaultName,
  onCancel,
  onConnected,
}: {
  defaultName: string
  onCancel: () => void
  onConnected: (channel: Channel) => void
}) {
  const { setSubject } = useSession()
  const [token, setToken] = useState('')
  const [name, setName] = useState(defaultName)
  const [tokenError, setTokenError] = useState<string | null>(null)
  const [found, setFound] = useState<string | null>(null)
  const [pending, setPending] = useState<'check' | 'connect' | null>(null)

  async function run<T>(kind: 'check' | 'connect', action: () => Promise<Result<T>>) {
    setPending(kind)
    setTokenError(null)
    setFound(null)
    try {
      const result = await action()
      setPending(null)
      if (result.kind === 'success') {
        return result.value
      }
      if (result.kind === 'unauthorized') {
        setSubject(null)
      } else {
        setTokenError(message(result))
      }
    } catch {
      setPending(null)
      setTokenError(failureMessage())
    }
    return null
  }

  async function handleCheck() {
    const username = await run('check', () => checkToken(token))
    if (username) {
      setFound(username)
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const channel = await run('connect', () => connectChannel(token, name))
    if (channel) {
      onConnected(channel)
    }
  }

  return (
    <Paper withBorder radius="md" p={{ base: 'md', sm: 'lg' }} bg="white">
      <form onSubmit={handleSubmit} noValidate>
        <Stack gap="md">
          <Title order={2} fz="lg">
            Подключить Telegram
          </Title>
          <List type="ordered" size="sm" c="dimmed">
            <List.Item>Создайте бота у @BotFather</List.Item>
            <List.Item>Скопируйте токен и вставьте ниже</List.Item>
          </List>
          <PasswordInput
            label="Токен бота"
            required
            autoComplete="off"
            value={token}
            onChange={(event) => {
              setToken(event.currentTarget.value)
              setFound(null)
            }}
            error={tokenError}
          />
          <TextInput
            label="Как назвать в Logos"
            placeholder="Telegram"
            maxLength={200}
            value={name}
            onChange={(event) => setName(event.currentTarget.value)}
          />
          <Group gap="sm">
            <Button
              variant="default"
              onClick={handleCheck}
              loading={pending === 'check'}
              disabled={!token.trim() || pending !== null}
            >
              Проверить подключение
            </Button>
            {found && (
              <Text size="sm" c="green" role="status">
                ✓ Бот найден: @{found}
              </Text>
            )}
          </Group>
          <Group gap="sm">
            <Button
              type="submit"
              loading={pending === 'connect'}
              disabled={!token.trim() || pending !== null}
            >
              Подключить
            </Button>
            <Button variant="default" onClick={onCancel} disabled={pending !== null}>
              Отмена
            </Button>
          </Group>
        </Stack>
      </form>
    </Paper>
  )
}
