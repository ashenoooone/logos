import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiPost } from './api-client'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.cookie = 'logos_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
})

describe('apiPost', () => {
  it('без cookie сначала получает CSRF-токен и отправляет его в X-CSRF-Token', async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(async () => json({ csrf_token: 'fresh' }))
      .mockImplementationOnce(async () => json({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    const response = await apiPost('/auth/manager/otp/request', { email: 'a@b.c' })

    expect(response).toEqual({ status: 200, data: { ok: true } })
    expect(fetchMock.mock.calls[0][0]).toBe('/auth/csrf')
    expect(fetchMock.mock.calls[0][1].method).toBe('GET')
    const [path, init] = fetchMock.mock.calls[1]
    expect(path).toBe('/auth/manager/otp/request')
    expect(init.method).toBe('POST')
    expect(init.headers['X-CSRF-Token']).toBe('fresh')
    expect(init.credentials).toBe('same-origin')
    expect(JSON.parse(init.body)).toEqual({ email: 'a@b.c' })
  })

  it('берёт токен из cookie logos_csrf без лишнего запроса', async () => {
    document.cookie = 'logos_csrf=from-cookie; path=/'
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    const response = await apiPost('/auth/logout')

    expect(response).toEqual({ status: 204, data: null })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0]).toEqual([
      '/auth/logout',
      expect.objectContaining({
        headers: expect.objectContaining({ 'X-CSRF-Token': 'from-cookie' }),
      }),
    ])
  })

  it('не отправляет POST, если CSRF-токен получить не удалось', async () => {
    const fetchMock = vi.fn(async () => json({ detail: 'error' }, 500))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiPost('/auth/logout')).rejects.toThrow('CSRF bootstrap failed')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
