import { Container, Paper, Stack, Text, Title } from '@mantine/core'
import type { ReactNode } from 'react'

/** Узкая карточка по центру экрана для входа, приглашения и восстановления. */
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
    <Container size={440} py={{ base: 32, sm: 80 }} px="md">
      <Paper withBorder radius="md" p={{ base: 'lg', sm: 'xl' }} bg="white">
        <Stack gap="lg">
          <Stack gap={4}>
            <Title order={1} fz={{ base: 24, sm: 28 }} lh={1.2}>
              {title}
            </Title>
            {description && (
              <Text size="sm" c="dimmed" lh={1.5}>
                {description}
              </Text>
            )}
          </Stack>
          {children}
        </Stack>
      </Paper>
    </Container>
  )
}
