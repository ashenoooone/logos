import { Alert, Avatar, Badge, Button, Group, Loader, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { useState } from 'react'

import { failureMessage } from '@/common/api-client'
import { useSession } from '@/modules/session'

import type { Manager } from '../api/managers'
import { useManagers } from '../hooks/use-managers'
import { InvitationModal, type InvitationOutcome } from './invitation-modal'

type Notice = { color: string; text: string }

/** Раздел «Сотрудники»: список менеджеров, добавление и повтор приглашения. */
export function ManagersPanel() {
  const { setSubject } = useSession()
  const { state, reload } = useManagers()
  const [modal, setModal] = useState<{ manager?: Manager } | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)

  function handleDone(outcome: InvitationOutcome) {
    setModal(null)
    if (outcome.kind === 'unauthorized') {
      setSubject(null)
      return
    }
    setNotice(describe(outcome))
    reload()
  }

  const managers = state.kind === 'ready' ? state.managers : []
  const pending = managers.filter((manager) => manager.status === 'pending')
  const active = managers.filter((manager) => manager.status === 'active')

  function invite(manager?: Manager) {
    setNotice(null)
    setModal(manager ? { manager } : {})
  }

  return (
    <Stack gap="xl">
      <Group justify="space-between" align="flex-end" wrap="wrap" gap="md">
        <Title order={1} fz={{ base: 32, sm: 44 }} lh={1.05}>
          Сотрудники
        </Title>
        <Button size="md" onClick={() => invite()}>
          Добавить менеджера
        </Button>
      </Group>

      {notice && (
        <Alert color={notice.color} role="status" withCloseButton onClose={() => setNotice(null)}>
          {notice.text}
        </Alert>
      )}

      {state.kind === 'loading' && <Loader aria-label="Загрузка списка" />}
      {state.kind === 'error' && (
        <Alert color="red" title="Не удалось загрузить список">
          <Stack gap="xs" align="flex-start">
            <span>{failureMessage(state.status)}</span>
            <Button size="xs" variant="default" onClick={reload}>
              Повторить
            </Button>
          </Stack>
        </Alert>
      )}

      {state.kind === 'ready' && (
        <SimpleGrid cols={{ base: 1, xs: 3 }} spacing="lg">
          <Tile tone="violet" value={managers.length} label="Всего в команде" />
          <Tile tone="green" value={active.length} label="Активны" />
          <Tile tone="orange" value={pending.length} label="Ждут пароль" />
        </SimpleGrid>
      )}

      {state.kind === 'ready' && managers.length === 0 && <Text c="dimmed">Менеджеров пока нет.</Text>}
      {managers.length > 0 && (
        <Stack gap={0} component="section" aria-label="Команда">
          <Title order={2} pb="sm" style={{ borderBottom: '2px solid var(--mantine-color-ink-6)' }}>
            Команда
          </Title>
          {/* Ожидающие пароль — первыми: по ним нужно действие. */}
          {[...pending, ...active].map((manager) => (
            <ManagerRow key={manager.id} manager={manager} onInvite={invite} />
          ))}
        </Stack>
      )}

      {modal && (
        <InvitationModal manager={modal.manager} onClose={() => setModal(null)} onDone={handleDone} />
      )}
    </Stack>
  )
}

/** Цветная плитка с числом — в стиле плиток главной, только без ссылки. */
function Tile({ tone, value, label }: { tone: 'violet' | 'green' | 'orange'; value: number; label: string }) {
  return (
    <div className={`logos-hub-tile logos-hub-stat logos-hub-${tone}`}>
      <Text component="span" className="logos-hub-title">
        {label}
      </Text>
      <p className="logos-hub-figure">
        <span className="logos-hub-number">{value}</span>
      </p>
    </div>
  )
}

/** Строка менеджера: аватар, имя крупно, email и дата, статус и действие. */
function ManagerRow({ manager, onInvite }: { manager: Manager; onInvite: (manager: Manager) => void }) {
  const isPending = manager.status === 'pending'
  return (
    <Group className="logos-row" justify="space-between" wrap="wrap" gap="md">
      <Group gap="md" wrap="nowrap" style={{ minWidth: 0 }}>
        <Avatar size="md" color="initials" name={manager.name} />
        <Stack gap={2} style={{ minWidth: 0 }}>
          <Text fz="lg" fw={500} style={{ overflowWrap: 'anywhere' }}>
            {manager.name}
          </Text>
          <Group gap="md" wrap="wrap">
            <Text size="sm" c="dimmed" style={{ overflowWrap: 'anywhere' }}>
              {manager.email}
            </Text>
            <Text size="sm" c="dimmed">
              менеджер, добавлен {new Date(manager.created_at).toLocaleDateString('ru-RU')}
            </Text>
          </Group>
        </Stack>
      </Group>
      <Group gap="sm" wrap="nowrap">
        <Badge color={isPending ? 'orange' : 'green'} variant="light">
          {isPending ? 'Ожидает пароль' : 'Активен'}
        </Badge>
        {isPending && (
          <Button size="xs" variant="default" onClick={() => onInvite(manager)}>
            Повторить приглашение
          </Button>
        )}
      </Group>
    </Group>
  )
}

function describe(outcome: Exclude<InvitationOutcome, { kind: 'unauthorized' }>): Notice {
  switch (outcome.kind) {
    case 'sent':
      return { color: 'green', text: `Приглашение отправлено на ${outcome.manager.email}.` }
    case 'delivery-failed':
      return {
        color: 'yellow',
        text: `Менеджер ${outcome.manager.name} сохранён, но письмо на ${outcome.manager.email} не отправлено: почтовый сервер недоступен. Повторите приглашение позже.`,
      }
    case 'already-accepted':
      return { color: 'blue', text: 'Менеджер уже задал пароль — приглашение больше не нужно.' }
    case 'not-found':
      return { color: 'red', text: 'Менеджер не найден. Список обновлён.' }
  }
}
