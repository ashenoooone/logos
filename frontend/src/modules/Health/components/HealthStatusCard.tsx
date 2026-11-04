import { Badge, Button, Group, Paper, Stack, Text } from '@mantine/core'

import { useHealthCheck, type HealthState } from '../hooks/useHealthCheck'

interface StatusPresentation {
  label: string
  color: string
  message: string
}

function present(state: HealthState): StatusPresentation {
  switch (state.kind) {
    case 'loading':
      return {
        label: 'Проверка',
        color: 'gray',
        message: 'Проверяем готовность сервиса…',
      }
    case 'ready':
      return {
        label: 'Готово',
        color: 'green',
        message: 'Сервис отвечает, схема базы данных готова.',
      }
    case 'database-not-ready':
      return {
        label: 'База не готова',
        color: 'yellow',
        message:
          'Сервис вернул HTTP 503: база данных недоступна или не готова. Проверьте путь к базе данных и выполните миграции, затем повторите проверку.',
      }
    case 'network-error':
      return {
        label: 'Нет связи',
        color: 'red',
        message:
          'Не удалось подключиться к сервису. Проверьте, что сервер запущен и доступен по этому адресу.',
      }
    case 'unexpected-http':
      return {
        label: 'Неожиданный ответ',
        color: 'red',
        message: `Сервис вернул HTTP ${state.status}. Это не подтверждает готовность.`,
      }
    case 'invalid-response':
      return {
        label: 'Некорректный ответ',
        color: 'red',
        message: `Сервис вернул HTTP ${state.status}, но тело ответа не подтверждает готовность.`,
      }
  }
}

export function HealthStatusCard() {
  const { state, retry } = useHealthCheck()
  const presentation = present(state)
  const pending = state.kind === 'loading'

  return (
    <Paper withBorder radius="md" p={{ base: 'lg', sm: 'xl' }} bg="white">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start" gap="sm">
          <Text fw={600}>Готовность сервиса</Text>
          <Badge variant="light" color={presentation.color}>
            {presentation.label}
          </Badge>
        </Group>

        <div role="status" aria-live="polite" aria-atomic="true">
          <Text size="sm" lh={1.6}>
            {presentation.message}
          </Text>
        </div>

        <Group justify="space-between" align="center" gap="sm">
          <Text size="xs" c="dimmed" ff="monospace">
            GET /health
          </Text>
          <Button size="xs" variant="default" onClick={retry} disabled={pending}>
            {pending ? 'Проверяем…' : 'Проверить снова'}
          </Button>
        </Group>
      </Stack>
    </Paper>
  )
}
