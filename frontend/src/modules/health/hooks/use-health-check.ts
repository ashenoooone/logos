import { useQuery } from '@tanstack/react-query'

import { healthQueryOptions, type HealthCheckResult } from '../api/health'

export type HealthState = { kind: 'loading' } | HealthCheckResult

export interface HealthCheckState {
  state: HealthState
  retry: () => void
}

export function useHealthCheck(): HealthCheckState {
  const query = useQuery(healthQueryOptions)

  const state: HealthState =
    query.isPending || query.isFetching
      ? { kind: 'loading' }
      : query.isError
        ? { kind: 'network-error' }
        : (query.data ?? { kind: 'network-error' })

  return { state, retry: () => void query.refetch() }
}
