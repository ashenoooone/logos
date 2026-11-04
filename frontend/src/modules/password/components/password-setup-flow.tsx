import {
  Alert,
  Anchor,
  Button,
  Center,
  List,
  Loader,
  PasswordInput,
  Stack,
  Text,
  TextInput,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { useState, type FormEvent } from 'react'

import { failureMessage } from '@/common/api-client'
import { CenteredCard } from '@/common/centered-card'
import { useSession } from '@/modules/session'

import { previewLinkQueryOptions, submitPassword, type LinkFlow } from '../api/password'
import { passwordRules } from '../api/password-policy'
import { useLinkToken } from '../hooks/use-link-token'

type State =
  | { kind: 'loading' }
  | { kind: 'form'; email: string; name?: string }
  | { kind: 'expired' }
  | { kind: 'error'; status?: number }

const TEXT: Record<LinkFlow, { title: string; expired: string }> = {
  invitation: {
    title: 'Задайте пароль',
    expired:
      'Ссылка уже использована или срок её действия истёк. Попросите администратора отправить новое приглашение.',
  },
  reset: {
    title: 'Новый пароль',
    expired:
      'Ссылка уже использована или срок её действия истёк. Запросите восстановление пароля ещё раз.',
  },
}

/** Экран по одноразовой ссылке: проверка ссылки, ввод пароля, вход после сохранения. */
export function PasswordSetupFlow({ flow }: { flow: LinkFlow }) {
  const token = useLinkToken()
  const [expired, setExpired] = useState(false)
  const query = useQuery({
    ...previewLinkQueryOptions(flow, token ?? ''),
    enabled: token !== null,
  })

  let state: State
  if (!token || expired) {
    state = { kind: 'expired' }
  } else if (query.isPending || query.isFetching) {
    state = { kind: 'loading' }
  } else if (query.isError || !query.data) {
    state = { kind: 'error' }
  } else if (query.data.kind === 'valid') {
    state = { kind: 'form', email: query.data.email, name: query.data.name }
  } else if (query.data.kind === 'expired') {
    state = { kind: 'expired' }
  } else {
    state = { kind: 'error', status: query.data.status }
  }

  switch (state.kind) {
    case 'loading':
      return (
        <Center mih="60vh">
          <Loader aria-label="Проверяем ссылку" />
        </Center>
      )
    case 'expired':
      return (
        <CenteredCard title="Ссылка устарела" description={TEXT[flow].expired}>
          {flow === 'reset' ? (
            <Anchor component={Link} to="/forgot-password">
              Запросить новую ссылку
            </Anchor>
          ) : (
            <Anchor component={Link} to="/login">
              Перейти ко входу
            </Anchor>
          )}
        </CenteredCard>
      )
    case 'error':
      return (
        <CenteredCard title="Не удалось проверить ссылку">
          <Alert color="red" role="alert">
            {failureMessage(state.status)} Обновите страницу по ссылке из письма.
          </Alert>
        </CenteredCard>
      )
    case 'form':
      return (
        <CenteredCard
          title={TEXT[flow].title}
          description={state.name ? `${state.name}, придумайте пароль для входа в Logos.` : undefined}
        >
          <PasswordForm
            flow={flow}
            token={token ?? ''}
            email={state.email}
            onExpired={() => setExpired(true)}
          />
        </CenteredCard>
      )
  }
}

function PasswordForm({
  flow,
  token,
  email,
  onExpired,
}: {
  flow: LinkFlow
  token: string
  email: string
  onExpired: () => void
}) {
  const { setSubject } = useSession()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const rules = passwordRules(password, confirmation)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    setServerError(null)
    setFailure(null)
    if (rules.some((rule) => !rule.ok)) {
      return
    }

    setPending(true)
    try {
      const result = await submitPassword(flow, token, password, confirmation)
      if (result.kind === 'success') {
        setSubject(result.subject)
        await navigate({ to: '/', replace: true })
        return
      }
      if (result.kind === 'expired') {
        onExpired()
        return
      }
      if (result.kind === 'invalid-password') {
        setServerError(result.message)
      } else {
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
        <TextInput label="Email" value={email} readOnly autoComplete="username" />
        <PasswordInput
          label="Пароль"
          autoComplete="new-password"
          required
          value={password}
          error={serverError}
          onChange={(event) => setPassword(event.currentTarget.value)}
        />
        <PasswordInput
          label="Повторите пароль"
          autoComplete="new-password"
          required
          value={confirmation}
          onChange={(event) => setConfirmation(event.currentTarget.value)}
        />
        <List size="sm" spacing={2} listStyleType="none" aria-label="Требования к паролю">
          {rules.map((rule) => (
            <List.Item key={rule.label}>
              <Text
                span
                size="sm"
                c={rule.ok ? 'green.8' : submitted ? 'red.7' : 'dimmed'}
                data-ok={rule.ok}
              >
                {rule.ok ? '✓' : '•'} {rule.label}
              </Text>
            </List.Item>
          ))}
        </List>
        {failure && (
          <Alert color="red" role="alert">
            {failure}
          </Alert>
        )}
        <Button type="submit" loading={pending}>
          Сохранить пароль
        </Button>
      </Stack>
    </form>
  )
}
