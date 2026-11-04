import { Anchor, Button, Group, Text } from '@mantine/core'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'

import { failureMessage } from '@/common/api-client'

import { logout } from '../api/session'
import { useSession } from '../hooks/use-session'

export function SessionHeader() {
  const { subject, setSubject } = useSession()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!subject) {
    return null
  }

  async function handleLogout() {
    setPending(true)
    setError(null)
    try {
      if (await logout()) {
        setSubject(null)
        return
      }
      setError('Не удалось выйти. Повторите попытку.')
    } catch {
      setError(failureMessage())
    }
    setPending(false)
  }

  const who =
    subject.type === 'administrator' ? 'Администратор' : `${subject.name} · ${subject.email}`

  return (
    <Group justify="space-between" wrap="wrap" gap="sm" px="md" py="sm">
      <Group gap="md" wrap="wrap">
        <Anchor component={Link} to="/" fw={600} c="dark" underline="never">
          Logos
        </Anchor>
        {subject.type === 'administrator' && (
          <Anchor component={Link} to="/employees" size="sm">
            Сотрудники
          </Anchor>
        )}
        {subject.type === 'manager' && (
          <Anchor component={Link} to="/profile" size="sm">
            Профиль
          </Anchor>
        )}
      </Group>
      <Group gap="sm" wrap="wrap">
        <Text size="sm" c="dimmed" style={{ overflowWrap: 'anywhere' }}>
          {who}
        </Text>
        <Button size="xs" variant="default" onClick={handleLogout} loading={pending}>
          Выйти
        </Button>
        {error && (
          <Text size="xs" c="red" role="alert">
            {error}
          </Text>
        )}
      </Group>
    </Group>
  )
}
