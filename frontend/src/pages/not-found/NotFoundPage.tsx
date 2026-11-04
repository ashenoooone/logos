import { Container, Stack, Text, Title } from '@mantine/core'
import { Link } from '@tanstack/react-router'

export function NotFoundPage() {
  return (
    <Container size={640} py={{ base: 48, sm: 96 }} px="md">
      <Stack gap="md">
        <Text
          size="xs"
          tt="uppercase"
          c="dimmed"
          style={{ letterSpacing: '0.12em' }}
        >
          Logos · техническая проверка
        </Text>
        <Title order={1} fz={{ base: 28, sm: 34 }} lh={1.1}>
          Страница не найдена
        </Title>
        <Text c="dimmed" lh={1.6}>
          Такого адреса в приложении нет. Возможно, ссылка устарела или содержит
          опечатку.
        </Text>
        <Link to="/" className="logos-link">
          На главную
        </Link>
      </Stack>
    </Container>
  )
}
