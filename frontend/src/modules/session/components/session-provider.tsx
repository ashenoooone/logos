import { Alert, Button, Center, Loader, Stack } from '@mantine/core'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { failureMessage } from '@/common/api-client'

import { fetchMe, type Subject } from '../api/session'
import { SessionContext } from '../hooks/use-session'

type State = { status: 'loading' } | { status: 'error' } | { status: 'ready'; subject: Subject | null }

/** Загружает текущего субъекта через GET /auth/me и не рендерит приложение до ответа. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    fetchMe(controller.signal)
      .then((subject) => setState({ status: 'ready', subject }))
      .catch(() => {
        if (!controller.signal.aborted) {
          setState({ status: 'error' })
        }
      })
    return () => controller.abort()
  }, [attempt])

  const subject = state.status === 'ready' ? state.subject : null
  const setSubject = useCallback(
    (next: Subject | null) => setState({ status: 'ready', subject: next }),
    [],
  )
  const value = useMemo(() => ({ subject, setSubject }), [subject, setSubject])

  if (state.status === 'loading') {
    return (
      <Center mih="100vh">
        <Loader aria-label="Загрузка" />
      </Center>
    )
  }

  if (state.status === 'error') {
    return (
      <Center mih="100vh" px="md">
        <Stack maw={420}>
          <Alert color="red" title="Не удалось проверить сессию">
            {failureMessage()}
          </Alert>
          <Button
            variant="default"
            onClick={() => {
              setState({ status: 'loading' })
              setAttempt((value) => value + 1)
            }}
          >
            Повторить
          </Button>
        </Stack>
      </Center>
    )
  }

  return <SessionContext value={value}>{children}</SessionContext>
}
