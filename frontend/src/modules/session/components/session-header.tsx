import { Anchor, Button, Group, Text } from '@mantine/core'
import { Link } from '@tanstack/react-router'
import { useState, type ReactNode } from 'react'

import { failureMessage } from '@/common/api-client'

import { logout } from '../api/session'
import { useSession } from '../hooks/use-session'

/** `managerLinks` — пункты меню менеджера из других модулей (подставляет app). */
export function SessionHeader({ managerLinks }: { managerLinks?: ReactNode }) {
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

  return (
    <Group justify="space-between" wrap="wrap" gap="sm" px="lg">
      <Group gap="lg" wrap="wrap">
        <Anchor component={Link} to="/" fw={700} fz="xl" c="white" underline="never" mr="sm">
          Logos
        </Anchor>
        {subject.type === 'administrator' && (
          <>
            <Link to="/employees" className="logos-nav">
              Сотрудники
            </Link>
            <Link to="/channels" className="logos-nav">
              Каналы
            </Link>
            <Link to="/tag-catalog" className="logos-nav">
              Теги
            </Link>
          </>
        )}
        {subject.type === 'manager' && (
          <>
            {managerLinks}
            <Link to="/profile" className="logos-nav">
              Профиль
            </Link>
          </>
        )}
      </Group>
      <Group gap="sm" wrap="wrap">
        {subject.type === 'administrator' ? (
          <Text size="sm" c="gray.4">
            Администратор
          </Text>
        ) : (
          <Text size="sm" style={{ overflowWrap: 'anywhere' }}>
            {subject.name}{' '}
            <Text span size="sm" c="gray.4">
              {subject.email}
            </Text>
          </Text>
        )}
        <Button size="compact-sm" variant="white" onClick={handleLogout} loading={pending}>
          Выйти
        </Button>
        {error && (
          <Text size="xs" c="red.3" role="alert">
            {error}
          </Text>
        )}
      </Group>
    </Group>
  )
}
