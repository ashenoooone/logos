import { Alert, Badge, Button, Group, Loader, Stack, Table, Text, Title } from '@mantine/core'
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

  return (
    <Stack gap="lg">
      <Group justify="space-between" wrap="wrap" gap="sm">
        <Title order={1} fz={{ base: 24, sm: 28 }}>
          Сотрудники
        </Title>
        <Button
          onClick={() => {
            setNotice(null)
            setModal({})
          }}
        >
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
      {state.kind === 'ready' && state.managers.length === 0 && (
        <Text c="dimmed">Менеджеров пока нет.</Text>
      )}
      {state.kind === 'ready' && state.managers.length > 0 && (
        <Table.ScrollContainer minWidth={640}>
          <Table verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Имя и фамилия</Table.Th>
                <Table.Th>Email</Table.Th>
                <Table.Th>Роль</Table.Th>
                <Table.Th>Статус</Table.Th>
                <Table.Th>Добавлен</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {state.managers.map((manager) => (
                <Table.Tr key={manager.id}>
                  <Table.Td>{manager.name}</Table.Td>
                  <Table.Td style={{ overflowWrap: 'anywhere' }}>{manager.email}</Table.Td>
                  <Table.Td>Менеджер</Table.Td>
                  <Table.Td>
                    {manager.status === 'active' ? (
                      <Badge color="green" variant="light">
                        Активен
                      </Badge>
                    ) : (
                      <Badge color="yellow" variant="light">
                        Ожидает пароль
                      </Badge>
                    )}
                  </Table.Td>
                  <Table.Td>{new Date(manager.created_at).toLocaleDateString('ru-RU')}</Table.Td>
                  <Table.Td>
                    {manager.status === 'pending' && (
                      <Button
                        size="xs"
                        variant="default"
                        onClick={() => {
                          setNotice(null)
                          setModal({ manager })
                        }}
                      >
                        Повторить приглашение
                      </Button>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      {modal && (
        <InvitationModal
          manager={modal.manager}
          onClose={() => setModal(null)}
          onDone={handleDone}
        />
      )}
    </Stack>
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
