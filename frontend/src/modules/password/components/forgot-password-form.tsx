import { Alert, Anchor, Button, Stack, Text, TextInput } from '@mantine/core'
import { Link } from '@tanstack/react-router'
import { useEffect, useState, type FormEvent } from 'react'

import { failureMessage } from '@/common/api-client'

import { requestPasswordReset } from '../api/password'

// Окно повтора по контракту: не чаще раза в 60 секунд на email.
const RESEND_COOLDOWN_SECONDS = 60

/** Запрос письма для восстановления: одинаковый ответ для любого email, повтор через 60 с. */
export function ForgotPasswordForm() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [cooldownUntil, setCooldownUntil] = useState(0)
  const [now, setNow] = useState(() => Date.now())
  const [emailError, setEmailError] = useState<string | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const secondsLeft = Math.max(0, Math.ceil((cooldownUntil - now) / 1000))

  useEffect(() => {
    if (cooldownUntil <= Date.now()) {
      return
    }
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [cooldownUntil])

  function startCooldown(seconds: number) {
    const current = Date.now()
    setNow(current)
    setCooldownUntil(current + seconds * 1000)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setEmailError(null)
    setFailure(null)
    if (!email.trim()) {
      setEmailError('Укажите email')
      return
    }

    setPending(true)
    try {
      const result = await requestPasswordReset(email)
      switch (result.kind) {
        case 'accepted':
          setSent(true)
          startCooldown(RESEND_COOLDOWN_SECONDS)
          break
        case 'cooldown':
          startCooldown(result.retryAfterSeconds)
          break
        case 'invalid-email':
          setEmailError('Некорректный email')
          break
        case 'delivery-failed':
          setFailure('Не удалось отправить письмо: почтовый сервер недоступен. Повторите позже.')
          break
        case 'failed':
          setFailure(failureMessage(result.status))
      }
    } catch {
      setFailure(failureMessage())
    }
    setPending(false)
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <Stack gap="md">
        <TextInput
          label="Email"
          type="email"
          autoComplete="username"
          required
          value={email}
          error={emailError}
          readOnly={sent}
          onChange={(event) => setEmail(event.currentTarget.value)}
        />
        {sent && (
          <Alert color="green" role="status">
            <Stack gap={4}>
              <span>
                Если аккаунт с этим email существует, мы отправили письмо со ссылкой для
                восстановления. Ссылка действует 1 час.
              </span>
              <span>Письмо не пришло? Проверьте папку «Спам».</span>
            </Stack>
          </Alert>
        )}
        {failure && (
          <Alert color="red" role="alert">
            {failure}
          </Alert>
        )}
        <Button type="submit" loading={pending} disabled={secondsLeft > 0}>
          {secondsLeft > 0
            ? `Отправить ещё раз через ${secondsLeft} с`
            : sent
              ? 'Отправить ещё раз'
              : 'Отправить ссылку'}
        </Button>
        <Text size="sm" ta="center">
          <Anchor component={Link} to="/login" size="sm">
            Вернуться ко входу
          </Anchor>
        </Text>
      </Stack>
    </form>
  )
}
