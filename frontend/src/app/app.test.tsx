import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { jsonResponse, MANAGER_SUBJECT } from './test/backend-mock'
import { renderApp } from './test/render-app'

/** Главная доступна только с сессией: /auth/me отвечает менеджером. */
function stubManager() {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      if (String(input) === '/auth/me') {
        return Promise.resolve(jsonResponse({ subject: MANAGER_SUBJECT }))
      }
      if (String(input) === '/conversations') {
        return Promise.resolve(jsonResponse({ conversations: [], unread_total: 0, last_incoming_id: null }))
      }
      return Promise.resolve(jsonResponse({ detail: 'Not Found' }, 404))
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('маршрутизация', () => {
  it('показывает понятную страницу для неизвестного адреса и ведёт на главную', async () => {
    stubManager()

    const user = userEvent.setup()
    renderApp('/unknown/address')

    expect(
      await screen.findByRole('heading', { name: 'Страница не найдена' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'На главную' }))

    expect(await screen.findByRole('heading', { name: 'Здравствуйте, Анна' })).toBeInTheDocument()
  })
})
