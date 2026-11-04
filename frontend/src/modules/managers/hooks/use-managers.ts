import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

import { useSession } from '@/modules/session'

import { managersQueryOptions, type Manager } from '../api/managers'

export type ManagersState =
  | { kind: 'loading' }
  | { kind: 'ready'; managers: Manager[] }
  | { kind: 'error'; status?: number }

export function useManagers() {
  const { setSubject } = useSession()
  const query = useQuery(managersQueryOptions)

  useEffect(() => {
    if (query.data?.kind === 'unauthorized') {
      setSubject(null) // сессия истекла или отозвана — guard уведёт на вход
    }
  }, [query.data, setSubject])

  let state: ManagersState
  if (query.isError) {
    state = { kind: 'error' }
  } else if (!query.data) {
    state = { kind: 'loading' }
  } else if (query.data.kind === 'success') {
    state = { kind: 'ready', managers: query.data.managers }
  } else if (query.data.kind === 'unauthorized') {
    state = { kind: 'loading' }
  } else {
    state = { kind: 'error', status: query.data.status }
  }

  return { state, reload: () => void query.refetch() }
}
