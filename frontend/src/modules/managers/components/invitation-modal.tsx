import { Alert, Button, Group, Modal, Stack, Text, TextInput } from '@mantine/core'
import { useState, type FormEvent } from 'react'

import { failureMessage } from '@/common/api-client'

import {
  createManager,
  resendInvitation,
  type InvitationResult,
  type Manager,
} from '../api/managers'

export type InvitationOutcome = Extract<
  InvitationResult,
  { kind: 'sent' | 'delivery-failed' | 'already-accepted' | 'not-found' | 'unauthorized' }
>

/**
 * Без `manager` — форма «Новый менеджер» (имя и email, роль фиксирована).
 * С `manager` — повтор приглашения ожидающему менеджеру с возможностью исправить email.
 */
export function InvitationModal({
  manager,
  onClose,
  onDone,
}: {
  manager?: Manager
  onClose: () => void
  onDone: (outcome: InvitationOutcome) => void
}) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState(manager?.email ?? '')
  const [errors, setErrors] = useState<{ name?: string; email?: string }>({})
  const [failure, setFailure] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const local = {
      name: !manager && !name.trim() ? 'Укажите имя и фамилию' : undefined,
      email: !email.trim() ? 'Укажите email' : undefined,
    }
    setErrors(local)
    setFailure(null)
    if (local.name || local.email) {
      return
    }

    setPending(true)
    try {
      const result = manager
        ? await resendInvitation(manager.id, email)
        : await createManager(name, email)
      if (result.kind === 'field') {
        setErrors({ [result.field]: result.message })
      } else if (result.kind === 'failed') {
        setFailure(failureMessage(result.status))
      } else {
        onDone(result)
        return
      }
    } catch {
      setFailure(failureMessage())
    }
    setPending(false)
  }

  return (
    <Modal
      opened
      onClose={onClose}
      title={manager ? 'Повторить приглашение' : 'Новый менеджер'}
      centered
    >
      <form onSubmit={handleSubmit} noValidate>
        <Stack gap="md">
          {manager ? (
            <Text size="sm">{manager.name}</Text>
          ) : (
            <TextInput
              label="Имя и фамилия"
              required
              data-autofocus
              value={name}
              error={errors.name}
              onChange={(event) => setName(event.currentTarget.value)}
            />
          )}
          <TextInput
            label="Email"
            type="email"
            required
            value={email}
            error={errors.email}
            description={
              manager
                ? 'Исправьте адрес при опечатке. Прежняя ссылка перестанет работать.'
                : undefined
            }
            onChange={(event) => setEmail(event.currentTarget.value)}
          />
          {!manager && (
            <Text size="sm" c="dimmed">
              Роль: менеджер. На email будет отправлено приглашение.
            </Text>
          )}
          {failure && (
            <Alert color="red" role="alert">
              {failure}
            </Alert>
          )}
          <Group justify="flex-end" gap="sm">
            <Button variant="default" onClick={onClose} disabled={pending}>
              Отмена
            </Button>
            <Button type="submit" loading={pending}>
              {manager ? 'Отправить' : 'Добавить'}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}
