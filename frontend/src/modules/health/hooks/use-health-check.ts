import { useCallback, useEffect, useState } from 'react'

import { checkHealth, type HealthCheckResult } from '../api/health'

export type HealthState = { kind: 'loading' } | HealthCheckResult

export interface HealthCheckState {
  state: HealthState
  retry: () => void
}

export function useHealthCheck(): HealthCheckState {
  const [state, setState] = useState<HealthState>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)

  const retry = useCallback(() => {
    setState({ kind: 'loading' })
    setAttempt((value) => value + 1)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    let active = true

    checkHealth(controller.signal)
      .then((result) => {
        if (active) {
          setState(result)
        }
      })
      .catch(() => {
        if (active) {
          setState({ kind: 'network-error' })
        }
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [attempt])

  return { state, retry }
}
