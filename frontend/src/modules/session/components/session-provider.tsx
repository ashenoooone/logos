import { Alert, Button, Center, Loader, Stack } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useMemo, type ReactNode } from 'react'

import { failureMessage } from '@/common/api-client'

import { meQueryOptions, type Subject } from '../api/session'
import { SessionContext } from '../hooks/use-session'

/** Загружает текущего субъекта через GET /auth/me и не рендерит приложение до ответа. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const query = useQuery(meQueryOptions)

  const setSubject = useCallback(
    (next: Subject | null) => queryClient.setQueryData(meQueryOptions.queryKey, next),
    [queryClient],
  )

  const subject = query.data ?? null
  const value = useMemo(() => ({ subject, setSubject }), [subject, setSubject])

  if (query.isPending || (query.isError && query.isFetching)) {
    return (
      <Center mih="100vh">
        <Loader aria-label="Загрузка" />
      </Center>
    )
  }

  if (query.isError) {
    return (
      <Center mih="100vh" px="md">
        <Stack maw={420}>
          <Alert color="red" title="Не удалось проверить сессию">
            {failureMessage()}
          </Alert>
          <Button variant="default" onClick={() => void query.refetch()}>
            Повторить
          </Button>
        </Stack>
      </Center>
    )
  }

  return <SessionContext value={value}>{children}</SessionContext>
}
