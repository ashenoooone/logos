import { Alert, Button, Group, Modal, Select, Stack, Textarea } from '@mantine/core'
import { useState, type FormEvent } from 'react'

import { failureMessage } from '@/common/api-client'

import { transferConversation, type TransferManager } from '../api/inbox'

/**
 * Окно «Передать» (#16): выбор коллеги и обязательный комментарий.
 * Менеджер не в смене показан, но выбрать его нельзя.
 */
export function TransferModal({
  conversationId,
  managers,
  loading,
  onClose,
  onDone,
}: {
  conversationId: number
  managers: TransferManager[]
  loading: boolean
  onClose: () => void
  onDone: () => void
}) {
  const [target, setTarget] = useState<string | null>(null)
  const [comment, setComment] = useState('')
  const [errors, setErrors] = useState<{ target?: string; comment?: string }>({})
  const [failure, setFailure] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const options = managers.map((manager) => ({
    value: String(manager.id),
    label: manager.on_shift === false ? `${manager.name} — не в смене` : manager.name,
    disabled: manager.on_shift === false,
  }))

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const local = {
      target: target === null ? 'Выберите менеджера' : undefined,
      comment: comment.trim() === '' ? 'Напишите комментарий' : undefined,
    }
    setErrors(local)
    setFailure(null)
    if (local.target || local.comment || target === null) {
      return
    }

    setPending(true)
    try {
      const result = await transferConversation(conversationId, Number(target), comment.trim())
      if (result.kind === 'field') {
        setErrors(result.field === 'comment' ? { comment: result.message } : { target: result.message })
      } else if (result.kind === 'pending') {
        setFailure('Передача уже ожидает принятия.')
      } else if (result.kind === 'not-found') {
        setFailure('Диалог не найден.')
      } else if (result.kind === 'failed') {
        setFailure(failureMessage(result.status))
      } else {
        onDone()
        return
      }
    } catch {
      setFailure(failureMessage())
    }
    setPending(false)
  }

  return (
    <Modal opened onClose={onClose} title="Передать обращение" centered>
      <form onSubmit={handleSubmit} noValidate>
        <Stack gap="md">
          <Select
            label="Кому передать"
            placeholder={loading ? 'Загрузка…' : 'Выберите менеджера'}
            data={options}
            value={target}
            error={errors.target}
            disabled={loading}
            searchable
            nothingFoundMessage="Нет коллег"
            onChange={(value) => {
              setTarget(value)
              setErrors((current) => ({ ...current, target: undefined }))
            }}
          />
          <Textarea
            label="Комментарий"
            required
            data-autofocus
            minRows={3}
            value={comment}
            error={errors.comment}
            placeholder="Что нужно сделать коллеге"
            onChange={(event) => {
              setComment(event.currentTarget.value)
              setErrors((current) => ({ ...current, comment: undefined }))
            }}
          />
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
              Передать
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}
