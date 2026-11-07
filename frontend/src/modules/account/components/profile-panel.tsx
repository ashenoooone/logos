import {
  Alert,
  Box,
  Button,
  Checkbox,
  List,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useState, type FormEvent, type ReactNode } from 'react'

import { failureMessage } from '@/common/api-client'
import { passwordRules } from '@/modules/password'
import { useSession, type Subject } from '@/modules/session'

import {
  changeName,
  changePassword,
  requestEmailChange,
  type FieldErrors,
  type SaveResult,
} from '../api/account'

/** Профиль менеджера: имя, email (с подтверждением), пароль. */
export function ProfilePanel() {
  const { subject } = useSession()
  if (subject?.type !== 'manager') {
    return null
  }
  return (
    <Stack gap="lg">
      <Title order={1}>Профиль</Title>
      <Stack gap={0} style={{ borderTop: '2px solid var(--mantine-color-ink-6)' }}>
        <NameForm name={subject.name} />
        <EmailForm email={subject.email} />
        <PasswordForm email={subject.email} />
      </Stack>
    </Stack>
  )
}

/** Раздел настроек: название слева, форма справа; на телефоне — друг под другом. */
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Box component="section" aria-label={title} className="logos-settings-row">
      <Title order={2}>{title}</Title>
      <Stack gap="md" maw={480}>
        {children}
      </Stack>
    </Box>
  )
}

/** Общая обработка отправки: ошибки полей, 401 → выход на вход, сбой связи. */
function useSubmit<T>(onSuccess: (value: T) => void) {
  const { setSubject } = useSession()
  const [pending, setPending] = useState(false)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [failure, setFailure] = useState<string | null>(null)

  async function submit(action: () => Promise<SaveResult<T>>) {
    setPending(true)
    setErrors({})
    setFailure(null)
    try {
      const result = await action()
      if (result.kind === 'success') {
        onSuccess(result.value)
      } else if (result.kind === 'invalid') {
        setErrors(result.errors)
      } else if (result.kind === 'unauthorized') {
        setSubject(null)
      } else {
        setFailure(failureMessage(result.status))
      }
    } catch {
      setFailure(failureMessage())
    }
    setPending(false)
  }

  return { pending, errors, setErrors, failure, submit }
}

function Failure({ message }: { message: string | null }) {
  return message ? (
    <Alert color="red" role="alert">
      {message}
    </Alert>
  ) : null
}

function NameForm({ name: initial }: { name: string }) {
  const { setSubject } = useSession()
  const [name, setName] = useState(initial)
  const [saved, setSaved] = useState(false)
  const { pending, errors, failure, submit } = useSubmit((subject: Subject) => {
    setSubject(subject)
    setSaved(true)
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSaved(false)
    void submit(() => changeName(name))
  }

  return (
    <Section title="Имя">
      <form onSubmit={handleSubmit} noValidate>
        <Stack gap="md">
          <TextInput
            label="Имя и фамилия"
            required
            maxLength={200}
            value={name}
            error={errors.name}
            onChange={(event) => setName(event.currentTarget.value)}
          />
          {saved && <Text size="sm" c="green.8">Имя сохранено.</Text>}
          <Failure message={failure} />
          <Button type="submit" loading={pending} w="fit-content">
            Сохранить
          </Button>
        </Stack>
      </form>
    </Section>
  )
}

function EmailForm({ email: current }: { email: string }) {
  const [email, setEmail] = useState('')
  const [pendingEmail, setPendingEmail] = useState<string | null>(null)
  const { pending, errors, failure, submit } = useSubmit((sentTo: string) => {
    setPendingEmail(sentTo)
    setEmail('')
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    void submit(() => requestEmailChange(email))
  }

  return (
    <Section title="Email">
      <Text size="sm">
        Текущий email: <b style={{ overflowWrap: 'anywhere' }}>{current}</b>
      </Text>
      {pendingEmail && (
        <Alert color="blue">
          Мы отправили ссылку на {pendingEmail}. Новый email начнёт работать после подтверждения,
          до этого входите по {current}. Ссылка действует 24 часа. Если письма нет, проверьте
          папку «Спам».
        </Alert>
      )}
      <form onSubmit={handleSubmit} noValidate>
        <Stack gap="md">
          <TextInput
            label="Новый email"
            type="email"
            autoComplete="email"
            required
            value={email}
            error={errors.email}
            onChange={(event) => setEmail(event.currentTarget.value)}
          />
          <Failure message={failure} />
          <Button type="submit" loading={pending} w="fit-content">
            Изменить email
          </Button>
        </Stack>
      </form>
    </Section>
  )
}

function PasswordForm({ email }: { email: string }) {
  const [current, setCurrent] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [signOut, setSignOut] = useState(true)
  const [submitted, setSubmitted] = useState(false)
  const [saved, setSaved] = useState(false)
  const rules = passwordRules(password, confirmation)
  const { pending, errors, setErrors, failure, submit } = useSubmit(() => {
    setSaved(true)
    setSubmitted(false)
    setCurrent('')
    setPassword('')
    setConfirmation('')
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    setSaved(false)
    if (!current) {
      setErrors({ current_password: 'Укажите текущий пароль.' })
      return
    }
    if (rules.some((rule) => !rule.ok)) {
      setErrors({})
      return
    }
    void submit(() =>
      changePassword({
        current_password: current,
        new_password: password,
        new_password_confirmation: confirmation,
        sign_out_other_devices: signOut,
      }),
    )
  }

  return (
    <Section title="Пароль">
      <form onSubmit={handleSubmit} noValidate>
        <Stack gap="md">
          {/* Скрытое имя пользователя помогает менеджеру паролей связать новый пароль с учёткой. */}
          <input type="email" value={email} autoComplete="username" readOnly hidden />
          <PasswordInput
            label="Текущий пароль"
            autoComplete="current-password"
            required
            value={current}
            error={errors.current_password}
            onChange={(event) => setCurrent(event.currentTarget.value)}
          />
          <PasswordInput
            label="Новый пароль"
            autoComplete="new-password"
            required
            value={password}
            error={errors.new_password}
            onChange={(event) => setPassword(event.currentTarget.value)}
          />
          <PasswordInput
            label="Повторите новый пароль"
            autoComplete="new-password"
            required
            value={confirmation}
            error={errors.new_password_confirmation}
            onChange={(event) => setConfirmation(event.currentTarget.value)}
          />
          <List size="sm" spacing={2} listStyleType="none" aria-label="Требования к паролю">
            {rules.map((rule) => (
              <List.Item key={rule.label}>
                <Text span size="sm" c={rule.ok ? 'green.8' : submitted ? 'red.7' : 'dimmed'}>
                  {rule.ok ? '✓' : '•'} {rule.label}
                </Text>
              </List.Item>
            ))}
          </List>
          <Checkbox
            label="Выйти на других устройствах"
            checked={signOut}
            onChange={(event) => setSignOut(event.currentTarget.checked)}
          />
          {saved && <Text size="sm" c="green.8">Пароль изменён.</Text>}
          <Failure message={failure} />
          <Button type="submit" loading={pending} w="fit-content">
            Изменить пароль
          </Button>
        </Stack>
      </form>
    </Section>
  )
}
