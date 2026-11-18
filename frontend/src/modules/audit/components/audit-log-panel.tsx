import {
  Alert,
  Button,
  Group,
  Loader,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { failureMessage } from '@/common/api-client'
import { useSession } from '@/modules/session'

import {
  AUDIT_ACTION_LABELS,
  actorValue,
  auditQueryOptions,
  exportAuditLog,
  type AuditAction,
  type AuditFilters,
} from '../api/audit'

const ACTIONS: AuditAction[] = ['login', 'logout', 'tag_deleted', 'export']

const DATE_TIME = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'medium' })

/** Раздел администратора «Журнал действий» (#18): фильтры, просмотр и CSV. */
export function AuditLogPanel() {
  const { setSubject } = useSession()
  const [filters, setFilters] = useState<AuditFilters>(() => defaultFilters())
  const [error, setError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const query = useQuery(auditQueryOptions(filters))

  const unauthorized = query.data?.status === 401
  useEffect(() => {
    if (unauthorized) {
      setSubject(null)
    }
  }, [unauthorized, setSubject])

  if (query.isPending || unauthorized) {
    return <Loader aria-label="Загрузка журнала" />
  }

  const page = query.data?.status === 200 ? query.data.data : undefined
  if (!page) {
    return (
      <Alert color="red" title="Не удалось загрузить журнал">
        <Button size="xs" variant="default" onClick={() => void query.refetch()}>
          Повторить
        </Button>
      </Alert>
    )
  }

  const actorOptions = [
    { value: '', label: 'Все сотрудники' },
    ...page.actors.map((actor) => ({
      value: actorValue(actor),
      label: actor.kind === 'administrator' ? `${actor.name} (администратор)` : actor.name,
    })),
  ]

  async function handleExport() {
    setExporting(true)
    setError(null)
    try {
      const result = await exportAuditLog(filters)
      if (result.status === 401) {
        setSubject(null)
        return
      }
      if (!result.blob) {
        setError(failureMessage(result.status))
        return
      }
      const url = URL.createObjectURL(result.blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'audit-log.csv'
      link.click()
      URL.revokeObjectURL(url)
      void query.refetch()
    } catch {
      setError(failureMessage())
    } finally {
      setExporting(false)
    }
  }

  return (
    <Stack gap="lg">
      <Stack gap={4}>
        <Title order={1}>Журнал действий</Title>
        <Text c="dimmed">
          Только просмотр: записи неизменяемы, хранятся 12 месяцев. По умолчанию — последние 7
          дней.
        </Text>
      </Stack>

      {error && (
        <Alert color="red" role="alert" withCloseButton onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Group align="flex-end" gap="sm" wrap="wrap">
        <Select
          label="Сотрудник"
          placeholder="Все сотрудники"
          data={actorOptions}
          value={filters.actor ?? ''}
          onChange={(value) => setFilters((current) => ({ ...current, actor: value || null }))}
          allowDeselect={false}
          w={{ base: '100%', sm: 240 }}
        />
        <Select
          label="Тип события"
          placeholder="Все типы"
          data={[
            { value: '', label: 'Все типы' },
            ...ACTIONS.map((action) => ({ value: action, label: AUDIT_ACTION_LABELS[action] })),
          ]}
          value={filters.action ?? ''}
          onChange={(value) =>
            setFilters((current) => ({ ...current, action: (value as AuditAction) || null }))
          }
          allowDeselect={false}
          w={{ base: '100%', sm: 200 }}
        />
        <TextInput
          type="date"
          label="С даты"
          value={filters.from ?? ''}
          onChange={(event) =>
            setFilters((current) => ({ ...current, from: event.currentTarget.value || null }))
          }
          w={{ base: '100%', sm: 170 }}
        />
        <TextInput
          type="date"
          label="По дату"
          value={filters.to ?? ''}
          onChange={(event) =>
            setFilters((current) => ({ ...current, to: event.currentTarget.value || null }))
          }
          w={{ base: '100%', sm: 170 }}
        />
        <Group gap="xs">
          <Button variant="default" onClick={() => setFilters(defaultFilters())}>
            Сбросить
          </Button>
          <Button loading={exporting} onClick={() => void handleExport()}>
            Выгрузить CSV
          </Button>
        </Group>
      </Group>

      <Text size="sm" c="dimmed" role="status">
        Найдено записей: {page.total}
        {page.truncated && ` · показаны последние ${page.events.length}`}
      </Text>

      {page.events.length === 0 ? (
        <Text c="dimmed">За выбранный период событий нет.</Text>
      ) : (
        <Table.ScrollContainer minWidth={760}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Дата и время</Table.Th>
                <Table.Th>Сотрудник</Table.Th>
                <Table.Th>Тип</Table.Th>
                <Table.Th>Событие</Table.Th>
                <Table.Th>IP</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {page.events.map((event) => (
                <Table.Tr key={event.id}>
                  <Table.Td style={{ whiteSpace: 'nowrap' }}>
                    {DATE_TIME.format(new Date(event.occurred_at))}
                  </Table.Td>
                  <Table.Td>{event.actor.name}</Table.Td>
                  <Table.Td>{AUDIT_ACTION_LABELS[event.action] ?? event.action}</Table.Td>
                  <Table.Td>{event.description}</Table.Td>
                  <Table.Td>{event.ip}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Stack>
  )
}

/** Период по умолчанию — последние 7 дней включительно. */
function defaultFilters(): AuditFilters {
  const today = new Date()
  const weekAgo = new Date(today)
  weekAgo.setDate(today.getDate() - 7)
  return { actor: null, action: null, from: isoDate(weekAgo), to: isoDate(today) }
}

function isoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}
