import { Alert, Button, Checkbox, PasswordInput, Stack, Text, TextInput } from '@mantine/core'
import { useEffect, useState, type FormEvent } from 'react'

import { failureMessage } from '@/common/api-client'

import {
  login,
  requestManagerOtp,
  verifyManagerOtp,
  type LoginKind,
  type LoginResult,
  type OtpRequestResult,
  type OtpVerifyResult,
} from '../api/session'
import { useSession } from '../hooks/use-session'

type AdminFailure = Exclude<LoginResult, { kind: 'success' }> | { kind: 'network' }
type OtpFailure = Exclude<OtpRequestResult, { kind: 'accepted' }> | { kind: 'network' }
type VerifyFailure = Exclude<OtpVerifyResult, { kind: 'success' }> | { kind: 'network' }
const RESEND_COOLDOWN_SECONDS = 60

/** Вход менеджера по коду и администратора по паролю. */
export function LoginForm({ kind }: { kind: LoginKind }) {
  return kind === 'manager' ? <ManagerLoginForm /> : <AdminLoginForm />
}

function ManagerLoginForm() {
  const { setSubject } = useSession()
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [remember, setRemember] = useState(false)
  const [codeRequested, setCodeRequested] = useState(false)
  const [cooldown, setCooldown] = useState(0)
  const [pending, setPending] = useState(false)
  const [failure, setFailure] = useState<OtpFailure | VerifyFailure | null>(null)
  const isCoolingDown = cooldown > 0
  useEffect(() => {
    if (!isCoolingDown) return
    const timer = window.setInterval(() => setCooldown((value) => Math.max(0, value - 1)), 1000)
    return () => window.clearInterval(timer)
  }, [isCoolingDown])

  async function requestCode(event?: FormEvent) {
    event?.preventDefault()
    if (pending) return
    setPending(true)
    setFailure(null)
    try {
      const result = await requestManagerOtp(email)
      if (result.kind === 'accepted') {
        setCodeRequested(true)
        setCooldown(RESEND_COOLDOWN_SECONDS)
        setCode('')
      } else {
        if (result.kind === 'cooldown') setCooldown(result.retryAfterSeconds)
        setFailure(result)
      }
    } catch {
      setFailure({ kind: 'network' })
    }
    setPending(false)
  }

  async function verifyCode(event: FormEvent) {
    event.preventDefault()
    if (pending || code.length !== 6) return
    setPending(true)
    setFailure(null)
    try {
      const result = await verifyManagerOtp(email, code, remember)
      if (result.kind === 'success') {
        setSubject(result.subject)
        return
      }
      setFailure(result)
    } catch {
      setFailure({ kind: 'network' })
    }
    setPending(false)
  }

  return codeRequested ? (
    <form onSubmit={verifyCode} noValidate>
      <Stack gap="md">
        <TextInput label="Email" type="email" value={email} readOnly />
        <Text size="sm" c="dimmed">
          Если учётная запись существует, мы отправили код на {email}. Проверьте также папку «Спам».
        </Text>
        <TextInput
          label="Код из письма"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          required
          value={code}
          onChange={(event) => setCode(event.currentTarget.value.replace(/\D/g, '').slice(0, 6))}
        />
        <Checkbox
          label="Запомнить меня"
          checked={remember}
          onChange={(event) => setRemember(event.currentTarget.checked)}
        />
        {failure && <OtpAlert failure={failure} />}
        <Button type="submit" loading={pending} disabled={code.length !== 6}>
          Подтвердить код
        </Button>
        <Button
          type="button"
          variant="subtle"
          disabled={pending || cooldown > 0}
          onClick={() => void requestCode()}
        >
          {cooldown > 0 ? `Отправить код ещё раз через ${cooldown} с` : 'Отправить код ещё раз'}
        </Button>
        <Button
          type="button"
          variant="subtle"
          disabled={pending}
          onClick={() => {
            setCodeRequested(false)
            setCode('')
            setCooldown(0)
            setFailure(null)
          }}
        >
          Изменить email
        </Button>
      </Stack>
    </form>
  ) : (
    <form onSubmit={requestCode} noValidate>
      <Stack gap="md">
        <TextInput
          label="Email"
          type="email"
          disabled={pending}
          required
          value={email}
          onChange={(event) => setEmail(event.currentTarget.value)}
        />
        {failure && <OtpAlert failure={failure} />}
        <Button type="submit" loading={pending} disabled={!email || cooldown > 0}>
          Получить код
        </Button>
      </Stack>
    </form>
  )
}

function OtpAlert({ failure }: { failure: OtpFailure | VerifyFailure }) {
  let message: string
  switch (failure.kind) {
    case 'invalid-email':
      message = 'Проверьте email.'
      break
    case 'delivery-failed':
      message = 'Не удалось отправить письмо. Попробуйте позже.'
      break
    case 'cooldown':
      message = `Повторите запрос через ${failure.retryAfterSeconds} с.`
      break
    case 'invalid':
      message = 'Неверный или просроченный код. Проверьте код и попробуйте ещё раз.'
      break
    case 'network':
      message = failureMessage()
      break
    default:
      message = failureMessage(failure.status)
  }
  return <Alert color="red" role="alert">{message}</Alert>
}

function AdminLoginForm() {
  const { setSubject } = useSession()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(false)
  const [pending, setPending] = useState(false)
  const [failure, setFailure] = useState<AdminFailure | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setFailure(null)
    try {
      const result = await login(identifier, password, remember)
      if (result.kind === 'success') {
        setSubject(result.subject)
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
        <TextInput
          label="Логин"
          autoComplete="username"
          required
          value={identifier}
          onChange={(event) => setIdentifier(event.currentTarget.value)}
        />
        <PasswordInput
          label="Пароль"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.currentTarget.value)}
        />
        <Checkbox
          label="Запомнить меня"
          checked={remember}
          onChange={(event) => setRemember(event.currentTarget.checked)}
        />
        {failure && <AdminLoginFailure failure={failure} />}
        <Button type="submit" loading={pending} disabled={!identifier || !password}>Войти</Button>
      </Stack>
    </form>
  )
}

function AdminLoginFailure({ failure }: { failure: AdminFailure }) {
  let message: string
  switch (failure.kind) {
    case 'invalid':
      message = `Неверный логин или пароль.${failure.attemptsRemaining === undefined ? '' : ` Осталось попыток: ${failure.attemptsRemaining}.`}`
      break
    case 'locked':
      message = `Вход заблокирован. ${retryAt(failure.retryAfterSeconds)}`
      break
    case 'network':
      message = failureMessage()
      break
    default:
      message = failureMessage(failure.status)
  }
  return <Alert color="red" role="alert">{message}</Alert>
}

function retryAt(seconds: number): string {
  const time = new Date(Date.now() + seconds * 1000).toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  })
  return `Попробовать снова можно в ${time} (через ${Math.ceil(seconds / 60)} мин).`
}
