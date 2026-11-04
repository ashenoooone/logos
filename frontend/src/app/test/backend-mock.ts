import { vi } from 'vitest'

export function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

export const CSRF_TOKEN = 'csrf-test-token'

type Handler = (body: unknown) => Response | Promise<Response>

export interface BackendCall {
  key: string
  body: unknown
  headers: Headers
  signal?: AbortSignal
}

/**
 * Подменяет fetch маршрутизатором по `"METHOD /path"`. По умолчанию: CSRF выдаётся и
 * кладётся в cookie, `/auth/me` — 401 (аноним), `/health` — готово.
 */
export function mockBackend(handlers: Record<string, Handler> = {}): BackendCall[] {
  const calls: BackendCall[] = []
  const defaults: Record<string, Handler> = {
    'GET /auth/csrf': () => {
      document.cookie = `logos_csrf=${CSRF_TOKEN}; path=/`
      return jsonResponse({ csrf_token: CSRF_TOKEN })
    },
    'GET /auth/me': () => jsonResponse({ detail: 'Unauthorized' }, 401),
    'GET /health': () => jsonResponse({ status: 'ok' }),
  }

  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const key = `${init?.method ?? 'GET'} ${String(input)}`
      const body = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
      calls.push({ key, body, headers: new Headers(init?.headers), signal: init?.signal ?? undefined })
      const handler = handlers[key] ?? defaults[key]
      return handler ? handler(body) : jsonResponse({ detail: 'Not Found' }, 404)
    }),
  )
  return calls
}

export function clearCookies() {
  for (const part of document.cookie.split(';')) {
    const name = part.split('=')[0].trim()
    if (name) {
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
    }
  }
}

export const MANAGER_SUBJECT = {
  type: 'manager',
  id: 1,
  name: 'Анна Петрова',
  email: 'anna@example.com',
} as const
