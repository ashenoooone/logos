import { Container, Paper, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import type { ReactNode } from 'react'

/**
 * Экран входа и приглашения: крупный заголовок слева, форма на
 * серой плашке справа; на телефоне — друг под другом.
 */
export function CenteredCard({
  title,
  description,
  children,
}: {
  title: string
  description?: ReactNode
  children: ReactNode
}) {
  return (
    <Container size={960} py={{ base: 32, sm: 96 }} px="md">
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={{ base: 'lg', sm: 64 }}>
        <Stack gap="md">
          <Text fw={700} fz="lg">
            Logos
          </Text>
          <Title order={1} fz={{ base: 32, sm: 44 }} lh={1.05} style={{ letterSpacing: '-0.02em' }}>
            {title}
          </Title>
          {description && (
            <Text c="dimmed" lh={1.5} maw={380}>
              {description}
            </Text>
          )}
        </Stack>
        <Paper bg="gray.0" p={{ base: 'lg', sm: 'xl' }}>
          {children}
        </Paper>
      </SimpleGrid>
    </Container>
  )
}
