import { useCallback, useEffect, useState } from 'react'

import { useSession } from '@/modules/session'

import { listManagers, type Manager } from '../api/managers'

export type ManagersState =
  | { kind: 'loading' }
  | { kind: 'ready'; managers: Manager[] }
  | { kind: 'error'; status?: number }

export function useManagers() {
  const { setSubject } = useSession()
  const [state, setState] = useState<ManagersState>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)

  const reload = useCallback(() => setAttempt((value) => value + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    listManagers(controller.signal)
      .then((result) => {
        if (result.kind === 'success') {
          setState({ kind: 'ready', managers: result.managers })
        } else if (result.kind === 'unauthorized') {
          setSubject(null) // сессия истекла или отозвана — guard уведёт на вход
        } else {
          setState({ kind: 'error', status: result.status })
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setState({ kind: 'error' })
        }
      })
    return () => controller.abort()
  }, [attempt, setSubject])

  return { state, reload }
}
