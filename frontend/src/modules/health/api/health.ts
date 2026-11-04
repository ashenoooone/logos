import { queryOptions } from '@tanstack/react-query'

export const HEALTH_ENDPOINT = '/health'

export type HealthCheckResult =
  | { kind: 'ready' }
  | { kind: 'database-not-ready' }
  | { kind: 'unexpected-http'; status: number }
  | { kind: 'invalid-response'; status: number }
  | { kind: 'network-error' }

export async function checkHealth(signal: AbortSignal): Promise<HealthCheckResult> {
  let response: Response

  try {
    response = await fetch(HEALTH_ENDPOINT, {
      method: 'GET',
      headers: { accept: 'application/json' },
      cache: 'no-store',
      signal,
    })
  } catch (error) {
    if (signal.aborted) {
      throw error
    }
    return { kind: 'network-error' }
  }

  if (response.status === 503) {
    return (await isDatabaseNotReadyResponse(response, signal))
      ? { kind: 'database-not-ready' }
      : { kind: 'unexpected-http', status: response.status }
  }

  if (response.status !== 200) {
    return { kind: 'unexpected-http', status: response.status }
  }

  let body: unknown
  try {
    body = await response.json()
  } catch (error) {
    if (signal.aborted) {
      throw error
    }
    return { kind: 'invalid-response', status: response.status }
  }

  if (isReadyBody(body)) {
    return { kind: 'ready' }
  }

  return { kind: 'invalid-response', status: response.status }
}

export const healthQueryOptions = queryOptions({
  queryKey: ['health'],
  queryFn: ({ signal }) => checkHealth(signal),
  retry: false,
})

async function isDatabaseNotReadyResponse(
  response: Response,
  signal: AbortSignal,
): Promise<boolean> {
  let body: unknown
  try {
    body = await response.json()
  } catch (error) {
    if (signal.aborted) {
      throw error
    }
    return false
  }

  return isDatabaseNotReadyBody(body)
}

function isDatabaseNotReadyBody(value: unknown): value is { detail: 'Database is not ready' } {
  return (
    typeof value === 'object' &&
    value !== null &&
    'detail' in value &&
    value.detail === 'Database is not ready'
  )
}

function isReadyBody(value: unknown): value is { status: 'ok' } {
  return (
    typeof value === 'object' &&
    value !== null &&
    'status' in value &&
    value.status === 'ok'
  )
}
