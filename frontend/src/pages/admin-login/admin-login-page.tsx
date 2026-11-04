import { Anchor, Text } from '@mantine/core'
import { Link } from '@tanstack/react-router'

import { CenteredCard } from '@/common/centered-card'
import { LoginForm } from '@/modules/session'

export function AdminLoginPage() {
  return (
    <CenteredCard
      title="Вход администратора"
      description="Логин и пароль, заданные при развёртывании. Восстановления пароля для администратора нет."
    >
      <LoginForm kind="administrator" />
      <Text size="xs" c="dimmed" ta="center">
        <Anchor component={Link} to="/login" size="xs" c="dimmed">
          Вход менеджера
        </Anchor>
      </Text>
    </CenteredCard>
  )
}
