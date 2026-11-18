import { Alert, Anchor, Badge, Box, Button, Group, Loader, Paper, SegmentedControl, Stack, Text } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { failureMessage } from '@/common/api-client'
import { channelLabel } from '@/common/channel-label'

import { clientHistoryQueryOptions, type ClientAppeal } from '../api/inbox'

// Периоды истории обращений (#13); по умолчанию 30 дней.
const PERIODS = [
  { label: '7 дней', value: '7' },
  { label: '30 дней', value: '30' },
  { label: 'Год', value: '365' },
]
const DEFAULT_PERIOD = '30'
const DAY_MS = 24 * 60 * 60 * 1000

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' }).replace('.', '')
}

/** Панель «Клиент»: период и прошлые обращения клиента одним таймлайном (#13). */
export function ClientPanel({
  conversationId,
  onOpen,
}: {
  conversationId: number
  onOpen: (appeal: ClientAppeal) => void
}) {
  const query = useQuery(clientHistoryQueryOptions(conversationId))
  const [period, setPeriod] = useState(DEFAULT_PERIOD)

  const data = query.data?.kind === 'success' ? query.data.value : null
  const since = Date.now() - Number(period) * DAY_MS
  const appeals = data?.appeals ?? []
  const visible = appeals.filter((appeal) => Date.parse(appeal.started_at) >= since)

  return (
    <Stack gap="sm" p="md" h="100%" style={{ overflowY: 'auto' }}>
      <Box>
        <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
          Клиент
        </Text>
        {data && <Text fw={600}>{data.client.name}</Text>}
      </Box>

      <Text size="sm" fw={600}>
        История обращений
      </Text>
      <SegmentedControl
        size="xs"
        fullWidth
        value={period}
        onChange={setPeriod}
        data={PERIODS}
        aria-label="Период истории"
      />

      {query.isPending && <Loader size="sm" aria-label="Загрузка истории" />}

      {!query.isPending && data === null && (
        <Alert color="red" role="alert" title="Не удалось загрузить историю">
          <Group gap="xs">
            <Text size="sm">{query.data?.kind === 'failed' ? failureMessage(query.data.status) : failureMessage()}</Text>
            <Button size="compact-xs" variant="default" onClick={() => void query.refetch()}>
              Повторить
            </Button>
          </Group>
        </Alert>
      )}

      {data && appeals.length === 0 && (
        <Text size="sm" c="dimmed">
          Обращений пока нет
        </Text>
      )}

      {data && appeals.length > 0 && (
        <>
          {visible.length === 0 && (
            <Text size="sm" c="dimmed">
              За выбранный период обращений нет — смените период.
            </Text>
          )}
          {visible.map((appeal) => (
            <Paper key={appeal.id} withBorder p="xs">
              <Stack gap={4}>
                <Group justify="space-between" gap="xs" wrap="nowrap">
                  <Text size="xs" c="dimmed">
                    {formatDate(appeal.started_at)}
                  </Text>
                  <Badge size="xs" variant="outline" color="gray">
                    {channelLabel(appeal.channel)}
                  </Badge>
                </Group>
                <Text size="sm" fw={500} lineClamp={2}>
                  {appeal.topic}
                </Text>
                <Group justify="space-between" gap="xs" wrap="nowrap">
                  <Text size="xs" c="dimmed">
                    Закрыто · {formatDate(appeal.ended_at)}
                  </Text>
                  <Anchor component="button" type="button" size="xs" onClick={() => onOpen(appeal)}>
                    Открыть →
                  </Anchor>
                </Group>
              </Stack>
            </Paper>
          ))}
          <Text size="xs" c="dimmed">
            Показаны {visible.length} из {appeals.length}
          </Text>
        </>
      )}
    </Stack>
  )
}
