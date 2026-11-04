import { afterEach, describe, expect, it, vi } from 'vitest'

import { checkHealth } from './health'

afterEach(() => {
  vi.unstubAllGlobals()
})

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

describe('checkHealth', () => {
  it('считает сервис готовым только при 200 и status "ok"', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ status: 'ok' })),
    )

    await expect(checkHealth(new AbortController().signal)).resolves.toEqual({
      kind: 'ready',
    })
  })

  it('распознаёт 503 как неготовую базу данных', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ detail: 'Database is not ready' }, 503)),
    )

    await expect(checkHealth(new AbortController().signal)).resolves.toEqual({
      kind: 'database-not-ready',
    })
  })

  it('не считает 503 диагнозом базы при постороннем теле ответа', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ detail: 'Service shutting down' }, 503)),
    )

    await expect(checkHealth(new AbortController().signal)).resolves.toEqual({
      kind: 'unexpected-http',
      status: 503,
    })
  })

  it('не считает 503 диагнозом базы при нечитаемом теле ответа', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response('<!doctype html><h1>Service Unavailable</h1>', {
            status: 503,
            headers: { 'content-type': 'text/html' },
          }),
      ),
    )

    await expect(checkHealth(new AbortController().signal)).resolves.toEqual({
      kind: 'unexpected-http',
      status: 503,
    })
  })

  it.each([500, 502])(
    'передаёт прочие HTTP-ошибки со статусом %i, не выдавая их за успех',
    async (status) => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () => new Response('', { status })),
      )

      await expect(checkHealth(new AbortController().signal)).resolves.toEqual({
        kind: 'unexpected-http',
        status,
      })
    },
  )

  it('не считает успехом 200 с посторонним телом', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ status: 'degraded' })),
    )

    await expect(checkHealth(new AbortController().signal)).resolves.toEqual({
      kind: 'invalid-response',
      status: 200,
    })
  })

  it('не считает успехом 200 с нечитаемым телом', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('not json', { status: 200 })),
    )

    await expect(checkHealth(new AbortController().signal)).resolves.toEqual({
      kind: 'invalid-response',
      status: 200,
    })
  })

  it('возвращает сетевую ошибку при отказе запроса', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )

    await expect(checkHealth(new AbortController().signal)).resolves.toEqual({
      kind: 'network-error',
    })
  })

  it('пробрасывает отмену запроса, а не маскирует её сетевой ошибкой', async () => {
    const controller = new AbortController()
    vi.stubGlobal(
      'fetch',
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        const { promise, reject } = Promise.withResolvers<Response>()
        init?.signal?.addEventListener('abort', () => {
          reject(new DOMException('Aborted', 'AbortError'))
        })
        return promise
      }),
    )

    const pending = checkHealth(controller.signal)
    controller.abort()

    await expect(pending).rejects.toThrow()
  })
})
