import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { renderApp } from './test/render-app'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('главный экран', () => {
  it('показывает загрузку, затем готовность по успешному ответу', async () => {
    const { promise, resolve } = Promise.withResolvers<Response>()
    vi.stubGlobal('fetch', vi.fn(() => promise))

    renderApp()

    expect(await screen.findByText('Проверяем готовность сервиса…')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Проверяем…' })).toBeDisabled()

    resolve(jsonResponse({ status: 'ok' }))

    expect(
      await screen.findByText('Сервис отвечает, схема базы данных готова.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Проверить снова' })).toBeEnabled()
  })

  it('показывает неготовую базу данных при HTTP 503 отдельно от успеха', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ detail: 'Database is not ready' }, 503)),
    )

    renderApp()

    expect(
      await screen.findByText(/HTTP 503: база данных недоступна или не готова/),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('Сервис отвечает, схема базы данных готова.'),
    ).not.toBeInTheDocument()
  })

  it('показывает сетевую ошибку, когда запрос отклонён', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )

    renderApp()

    expect(
      await screen.findByText(/Не удалось подключиться к сервису/),
    ).toBeInTheDocument()
    expect(screen.queryByText(/HTTP 503/)).not.toBeInTheDocument()
  })

  it('показывает прочий HTTP-ответ как неожиданный, не называя его сетевой ошибкой', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('', { status: 500 })),
    )

    renderApp()

    expect(
      await screen.findByText(
        'Сервис вернул HTTP 500. Это не подтверждает готовность.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Не удалось подключиться/)).not.toBeInTheDocument()
    expect(screen.queryByText(/HTTP 503/)).not.toBeInTheDocument()
  })

  it('не подтверждает готовность по 200 с некорректным телом', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('not json', { status: 200 })),
    )

    renderApp()

    expect(
      await screen.findByText(/тело ответа не подтверждает готовность/),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('Сервис отвечает, схема базы данных готова.'),
    ).not.toBeInTheDocument()
  })

  it('повторяет проверку вручную и блокирует кнопку до ответа', async () => {
    const second = Promise.withResolvers<Response>()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: 'Database is not ready' }, 503))
      .mockImplementationOnce(() => second.promise)
    vi.stubGlobal('fetch', fetchMock)

    renderApp()
    expect(await screen.findByText(/HTTP 503/)).toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Проверить снова' }))

    expect(await screen.findByText('Проверяем готовность сервиса…')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Проверяем…' })).toBeDisabled()
    expect(fetchMock).toHaveBeenCalledTimes(2)

    second.resolve(jsonResponse({ status: 'ok' }))

    expect(
      await screen.findByText('Сервис отвечает, схема базы данных готова.'),
    ).toBeInTheDocument()
  })

  it('отменяет запрос при уходе со страницы', async () => {
    let signal: AbortSignal | undefined
    const pending = Promise.withResolvers<Response>()
    vi.stubGlobal(
      'fetch',
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        signal = init?.signal ?? undefined
        return pending.promise
      }),
    )

    const view = renderApp()
    expect(await screen.findByText('Проверяем готовность сервиса…')).toBeInTheDocument()
    expect(signal?.aborted).toBe(false)

    view.unmount()

    expect(signal?.aborted).toBe(true)
  })
})

describe('маршрутизация', () => {
  it('показывает понятную страницу для неизвестного адреса и ведёт на главную', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ status: 'ok' })),
    )

    const user = userEvent.setup()
    renderApp('/unknown/address')

    expect(
      await screen.findByRole('heading', { name: 'Страница не найдена' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'На главную' }))

    expect(await screen.findByRole('heading', { name: 'Logos' })).toBeInTheDocument()
    expect(
      await screen.findByText('Сервис отвечает, схема базы данных готова.'),
    ).toBeInTheDocument()
  })
})
