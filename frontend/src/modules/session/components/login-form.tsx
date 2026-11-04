import {
  Alert,
  Anchor,
  Button,
  Checkbox,
  Group,
  PasswordInput,
  Stack,
  TextInput,
} from '@mantine/core'
import { Link } from '@tanstack/react-router'
import { useState, type FormEvent } from 'react'

import { failureMessage } from '@/common/api-client'

import { login, type LoginKind, type LoginResult } from '../api/session'
import { useSession } from '../hooks/use-session'

type Failure = Exclude<LoginResult, { kind: 'success' }> | { kind: 'network' }

/** Форма входа менеджера (email) или администратора (CLI-логин). */
export function LoginForm({ kind }: { kind: LoginKind }) {
  const { setSubject } = useSession()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(false)
  const [pending, setPending] = useState(false)
  const [failure, setFailure] = useState<Failure | null>(null)
  const isManager = kind === 'manager'

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setFailure(null)
    try {
      const result = await login(kind, identifier, password, remember)
      if (result.kind === 'success') {
        setSubject(result.subject) // guard анонимных страниц уведёт на главную
        return
      }
      setFailure(result)
    } catch {
      setFailure({ kind: 'network' })
    }
    setPending(false)
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <Stack gap="md">
        {isManager ? (
          <TextInput
            label="Email"
            type="email"
            autoComplete="username"
            required
            value={identifier}
            onChange={(event) => setIdentifier(event.currentTarget.value)}
          />
        ) : (
          <TextInput
            label="Логин"
            autoComplete="username"
            required
            value={identifier}
            onChange={(event) => setIdentifier(event.currentTarget.value)}
          />
        )}
        <PasswordInput
          label="Пароль"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.currentTarget.value)}
        />
        <Group justify="space-between" wrap="wrap" gap="xs">
          <Checkbox
            label="Запомнить меня"
            checked={remember}
            onChange={(event) => setRemember(event.currentTarget.checked)}
          />
          {isManager && (
            <Anchor component={Link} to="/forgot-password" size="sm">
              Забыли пароль?
            </Anchor>
          )}
        </Group>

        {failure && <LoginFailure failure={failure} isManager={isManager} />}

        <Button type="submit" loading={pending} disabled={!identifier || !password}>
          Войти
        </Button>
      </Stack>
    </form>
  )
}

function LoginFailure({ failure, isManager }: { failure: Failure; isManager: boolean }) {
  switch (failure.kind) {
    case 'invalid':
      return (
        <Alert color="red" role="alert">
          {isManager ? 'Неверный email или пароль.' : 'Неверный логин или пароль.'}
          {failure.attemptsRemaining !== undefined &&
            ` Осталось попыток: ${failure.attemptsRemaining}.`}
        </Alert>
      )
    case 'locked':
      return (
        <Alert color="red" role="alert" title="Вход заблокирован">
          <Stack gap={4}>
            <span>Слишком много неверных попыток.</span>
            {failure.retryAfterSeconds !== undefined && (
              <span>{retryAt(failure.retryAfterSeconds)}</span>
            )}
            {isManager && (
              <Anchor component={Link} to="/forgot-password" size="sm">
                Восстановить пароль
              </Anchor>
            )}
          </Stack>
        </Alert>
      )
    case 'network':
      return (
        <Alert color="red" role="alert">
          {failureMessage()}
        </Alert>
      )
    case 'failed':
      return (
        <Alert color="red" role="alert">
          {failureMessage(failure.status)}
        </Alert>
      )
  }
}

function retryAt(seconds: number): string {
  const time = new Date(Date.now() + seconds * 1000).toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  })
  return `Попробовать снова можно в ${time} (через ${Math.ceil(seconds / 60)} мин).`
}
