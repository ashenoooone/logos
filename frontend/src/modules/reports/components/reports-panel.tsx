import {
  Alert,
  Button,
  Group,
  Loader,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { failureMessage } from '@/common/api-client'
import { managersQueryOptions } from '@/modules/managers'
import { useSession } from '@/modules/session'

import {
  buildReportCsv,
  formatDuration,
  formatNumber,
  formatPeriod,
  reportFileName,
} from '../api/report-csv'
import { reportQueryOptions, type ChannelFilter, type Report, type ReportFilters } from '../api/reports'

const EMPTY_FILTERS: ReportFilters = { from: '', to: '', managerId: '', channel: 'all' }

/** Раздел «Отчёты»: KPI, таблица по менеджерам и выгрузка тех же цифр в CSV (#17). */
export function ReportsPanel() {
  const { setSubject } = useSession()
  const [filters, setFilters] = useState<ReportFilters>(EMPTY_FILTERS)
  const reportQuery = useQuery(reportQueryOptions(filters))
  const managersQuery = useQuery(managersQueryOptions)

  const unauthorized = reportQuery.data?.kind === 'unauthorized'
  useEffect(() => {
    if (unauthorized) {
      setSubject(null)
    }
  }, [unauthorized, setSubject])

  const report = reportQuery.data?.kind === 'success' ? reportQuery.data.report : undefined
  const managers = managersQuery.data?.kind === 'success' ? managersQuery.data.managers : []
  const from = filters.from || report?.period.from || ''
  const to = filters.to || report?.period.to || ''
  const managerOptions = [
    { value: '', label: 'Все менеджеры' },
    ...managers.map((manager) => ({ value: String(manager.id), label: manager.name })),
  ]

  function update(patch: Partial<ReportFilters>) {
    setFilters((current) => ({ ...current, ...patch }))
  }

  function download() {
    if (!report || report.empty) {
      return
    }
    const url = URL.createObjectURL(
      new Blob([buildReportCsv(report)], { type: 'text/csv;charset=utf-8' }),
    )
    const link = document.createElement('a')
    link.href = url
    link.download = reportFileName(report)
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Stack gap="xl">
      <Group justify="space-between" align="flex-end" wrap="wrap" gap="md">
        <Stack gap="xs">
          <Title order={1} fz={{ base: 32, sm: 44 }} lh={1.05}>
            Отчёты
          </Title>
          <Text c="dimmed" fz="lg">
            Статистика работы менеджеров: обращения, время ответа и закрытые диалоги.
          </Text>
        </Stack>
        <Button
          size="md"
          onClick={download}
          disabled={!report || report.empty || reportQuery.isFetching}
        >
          Выгрузить в CSV
        </Button>
      </Group>

      <Paper p="lg" bg="gray.0">
        <Group align="flex-end" gap="md" wrap="wrap">
          <TextInput
            type="date"
            label="Период с"
            value={from}
            max={to || undefined}
            onChange={(event) => update({ from: event.currentTarget.value })}
          />
          <TextInput
            type="date"
            label="по"
            value={to}
            min={from || undefined}
            onChange={(event) => update({ to: event.currentTarget.value })}
          />
          <Select
            label="Менеджер"
            data={managerOptions}
            value={filters.managerId}
            onChange={(value) => update({ managerId: value ?? '' })}
            allowDeselect={false}
            w={{ base: '100%', sm: 240 }}
          />
          <Select
            label="Канал"
            data={[
              { value: 'all', label: 'Все каналы' },
              { value: 'telegram', label: 'Telegram' },
            ]}
            value={filters.channel}
            onChange={(value) => update({ channel: (value ?? 'all') as ChannelFilter })}
            allowDeselect={false}
            w={{ base: '100%', sm: 180 }}
          />
        </Group>
      </Paper>

      {reportQuery.isPending && <Loader aria-label="Загрузка статистики" />}

      {reportQuery.data?.kind === 'invalid-period' && (
        <Alert color="red">Начало периода позже конца. Исправьте даты.</Alert>
      )}

      {reportQuery.data?.kind === 'failed' && (
        <Alert color="red" title="Не удалось загрузить статистику">
          <Stack gap="xs" align="flex-start">
            <span>{failureMessage(reportQuery.data.status)}</span>
            <Button size="xs" variant="default" onClick={() => void reportQuery.refetch()}>
              Повторить
            </Button>
          </Stack>
        </Alert>
      )}

      {report && report.empty && <EmptyState report={report} />}

      {report && !report.empty && (
        <>
          <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="lg">
            <StatTile
              tone="violet"
              label="Обращений"
              value={formatNumber(report.kpi.conversations)}
              hint={formatPeriod(report.period.from, report.period.to)}
            />
            <StatTile
              tone="green"
              label="Среднее время ответа"
              value={formatDuration(report.kpi.average_response_seconds)}
              hint="от входящего до первого ответа"
            />
            <StatTile
              tone="orange"
              label="Закрыто"
              value={formatNumber(report.kpi.closed)}
              hint={`${report.kpi.closed_percent}% от обращений`}
            />
          </SimpleGrid>

          <Paper p="lg" withBorder>
            <Stack gap="md">
              <Group justify="space-between" align="baseline" wrap="wrap">
                <Title order={2}>По менеджерам</Title>
                <Text size="sm" c="dimmed">
                  {formatPeriod(report.period.from, report.period.to)}
                </Text>
              </Group>
              <Table.ScrollContainer minWidth={720}>
                <Table highlightOnHover verticalSpacing="sm">
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Менеджер</Table.Th>
                      <Table.Th ta="right">Обращений</Table.Th>
                      <Table.Th ta="right">Ср. ответ</Table.Th>
                      <Table.Th ta="right">Закрыто</Table.Th>
                      <Table.Th ta="right">Доля</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {report.managers.map((manager) => (
                      <Table.Tr key={manager.id ?? 'unanswered'} style={{ opacity: manager.conversations === 0 ? 0.45 : 1 }}>
                        <Table.Td>{manager.name}</Table.Td>
                        <Table.Td ta="right">{manager.conversations}</Table.Td>
                        <Table.Td ta="right">
                          {formatDuration(manager.average_response_seconds)}
                        </Table.Td>
                        <Table.Td ta="right">{manager.closed}</Table.Td>
                        <Table.Td ta="right">
                          {manager.conversations === 0 ? '—' : `${manager.closed_percent}%`}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                  <Table.Tfoot>
                    <Table.Tr>
                      <Table.Th>Итого</Table.Th>
                      <Table.Th ta="right">{report.kpi.conversations}</Table.Th>
                      <Table.Th ta="right">
                        {formatDuration(report.kpi.average_response_seconds)}
                      </Table.Th>
                      <Table.Th ta="right">{report.kpi.closed}</Table.Th>
                      <Table.Th ta="right">{report.kpi.closed_percent}%</Table.Th>
                    </Table.Tr>
                  </Table.Tfoot>
                </Table>
              </Table.ScrollContainer>
              <Text size="sm" c="dimmed">
                Цифры считаются по обращениям за выбранный период; границы периода — в часовом
                поясе компании ({report.period.timezone}). Закрыто — последнее сообщение периода
                оставил менеджер.
              </Text>
            </Stack>
          </Paper>
        </>
      )}
    </Stack>
  )
}

function EmptyState({ report }: { report: Report }) {
  const who = report.filters.manager_name ?? 'Все менеджеры'
  return (
    <Paper p="xl" withBorder style={{ borderStyle: 'dashed' }}>
      <Stack gap="xs" align="center" ta="center">
        <Title order={2}>Данных за период нет</Title>
        <Text c="dimmed">
          {who} · {formatPeriod(report.period.from, report.period.to)}
        </Text>
        <Text>Измените период или менеджера — нули не показываем.</Text>
      </Stack>
    </Paper>
  )
}

function StatTile({
  tone,
  label,
  value,
  hint,
}: {
  tone: 'violet' | 'green' | 'orange'
  label: string
  value: string
  hint: string
}) {
  return (
    <div className={`logos-hub-tile logos-hub-stat logos-hub-${tone}`}>
      <Text component="span" className="logos-hub-title">
        {label}
      </Text>
      <p className="logos-hub-figure">
        <span className="logos-hub-number">{value}</span>
      </p>
      <Text size="sm" opacity={0.85}>
        {hint}
      </Text>
    </div>
  )
}
