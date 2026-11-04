import { Container, Stack, Text, Title } from '@mantine/core'

import { HealthStatusCard } from '@/modules/health'

export function HomePage() {
  return (
    <Container size={640} py={{ base: 48, sm: 96 }} px="md">
      <Stack gap="xl">
        <Stack gap="xs">
          <Text
            size="xs"
            tt="uppercase"
            c="dimmed"
            style={{ letterSpacing: '0.12em' }}
          >
            Logos · техническая проверка
          </Text>
          <Title order={1} fz={{ base: 32, sm: 40 }} lh={1.1}>
            Logos
          </Title>
          <Text c="dimmed" maw={520} lh={1.6}>
            Служебный экран запуска. Проверяет, что клиент и сервер соединены и схема
            базы данных готова к работе.
          </Text>
        </Stack>

        <HealthStatusCard />

        <Text size="xs" c="dimmed" lh={1.6}>
          Проверяется только готовность схемы SQLite. Вход, сессии и внешние интеграции
          в этой версии ещё не реализованы.
        </Text>
      </Stack>
    </Container>
  )
}
