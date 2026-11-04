import { Anchor, Text } from '@mantine/core'
import { Link } from '@tanstack/react-router'

import { CenteredCard } from '@/common/centered-card'
import { LoginForm } from '@/modules/session'

export function LoginPage() {
  return (
    <CenteredCard title="Вход в Logos">
      <LoginForm kind="manager" />
      <Text size="xs" c="dimmed" ta="center">
        <Anchor component={Link} to="/login/admin" size="xs" c="dimmed">
          Вход администратора
        </Anchor>
      </Text>
    </CenteredCard>
  )
}
