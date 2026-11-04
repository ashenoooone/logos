import { Container, Stack, Text, Title } from '@mantine/core'

import { HealthStatusCard } from '@/modules/health'

export function HomePage() {
  return (
    <Container size={640} py={{ base: 32, sm: 64 }} px="md">
      <Stack gap="xl">
        <Stack gap="xs">
          <Title order={1} fz={{ base: 32, sm: 40 }} lh={1.1}>
            Logos
          </Title>
          <Text c="dimmed" maw={520} lh={1.6}>
            Вы вошли в систему. Каналы и переписка появятся в следующих версиях.
          </Text>
        </Stack>

        <HealthStatusCard />
      </Stack>
    </Container>
  )
}
