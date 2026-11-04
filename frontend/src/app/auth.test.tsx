import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  clearCookies,
  CSRF_TOKEN,
  jsonResponse,
  MANAGER_SUBJECT,
  mockBackend,
} from './test/backend-mock'
import { renderApp } from './test/render-app'

afterEach(() => {
  vi.unstubAllGlobals()
  clearCookies()
})

const ADMIN_SUBJECT = { type: 'administrator' }
const PENDING_MANAGER = {
  id: 7,
  name: 'Иван Сидоров',
  email: 'ivan@example.com',
  role: 'manager',
  status: 'pending',
  created_at: '2026-11-04T10:00:00Z',
}

describe('доступ по сессии', () => {
  it('без сессии ведёт на вход менеджера', async () => {
    mockBackend()
    renderApp('/')
    expect(await screen.findByRole('heading', { name: 'Вход в Logos' })).toBeInTheDocument()
  })

  it('менеджер не попадает в «Сотрудники» и не видит ссылку на раздел', async () => {
    mockBackend({ 'GET /auth/me': () => jsonResponse({ subject: MANAGER_SUBJECT }) })
    renderApp('/employees')
    expect(await screen.findByRole('heading', { name: 'Logos' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Сотрудники' })).not.toBeInTheDocument()
  })
})

describe('вход менеджера', () => {
  async function submitLogin() {
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/Email/), 'anna@example.com')
    await user.type(screen.getByLabelText(/Пароль/), 'wrong-password1')
    await user.click(screen.getByRole('button', { name: 'Войти' }))
    return user
  }

  it('показывает общую ошибку и оставшиеся попытки из ответа', async () => {
    mockBackend({
      'POST /auth/manager/login': () =>
        jsonResponse({ detail: 'Invalid credentials', attempts_remaining: 3 }, 401),
    })
    renderApp('/login')
    await submitLogin()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Неверный email или пароль. Осталось попыток: 3.',
    )
  })

  it('показывает блокировку, время повтора и восстановление пароля', async () => {
    mockBackend({
      'POST /auth/manager/login': () =>
        jsonResponse(
          { detail: 'Too many login attempts', attempts_remaining: 0, retry_after_seconds: 900 },
          423,
        ),
    })
    renderApp('/login')
    await submitLogin()
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Вход заблокирован')
    expect(alert).toHaveTextContent('через 15 мин')
    expect(within(alert).getByRole('link', { name: 'Восстановить пароль' })).toBeInTheDocument()
  })

  it('после входа показывает в шапке, кто вошёл, и выходит по «Выйти»', async () => {
    const calls = mockBackend({
      'POST /auth/manager/login': () => jsonResponse({ subject: MANAGER_SUBJECT }),
      'POST /auth/logout': () => new Response(null, { status: 204 }),
    })
    renderApp('/login')
    const user = await submitLogin()

    expect(await screen.findByText('Анна Петрова · anna@example.com')).toBeInTheDocument()
    const login = calls.find((call) => call.key === 'POST /auth/manager/login')
    expect(login?.body).toEqual({
      email: 'anna@example.com',
      password: 'wrong-password1',
      remember: false,
    })
    expect(login?.headers.get('X-CSRF-Token')).toBe(CSRF_TOKEN)

    await user.click(screen.getByRole('button', { name: 'Выйти' }))
    expect(await screen.findByRole('heading', { name: 'Вход в Logos' })).toBeInTheDocument()
  })
})

describe('приглашение', () => {
  it('отправляет токен из фрагмента только в теле, убирает его из адреса и входит', async () => {
    const calls = mockBackend({
      'POST /invitations/preview': () =>
        jsonResponse({ name: 'Анна Петрова', email: 'anna@example.com', expires_at: 'x' }),
      'POST /invitations/accept': () => jsonResponse({ subject: MANAGER_SUBJECT }),
    })
    const { router } = renderApp('/invitation#token=secret-token')

    const email = await screen.findByLabelText('Email')
    expect(email).toHaveValue('anna@example.com')
    expect(email).toHaveAttribute('readonly')
    expect(router.history.location.hash).toBe('')
    expect(calls.find((call) => call.key === 'POST /invitations/preview')?.body).toEqual({
      token: 'secret-token',
    })
    expect(calls.every((call) => !call.key.includes('secret-token'))).toBe(true)

    const user = userEvent.setup()
    await user.type(screen.getByLabelText(/^Пароль/), 'abc')
    await user.click(screen.getByRole('button', { name: 'Сохранить пароль' }))
    expect(calls.some((call) => call.key === 'POST /invitations/accept')).toBe(false)

    await user.type(screen.getByLabelText(/^Пароль/), 'defgh1')
    await user.type(screen.getByLabelText(/Повторите пароль/), 'abcdefgh1')
    await user.click(screen.getByRole('button', { name: 'Сохранить пароль' }))

    expect(await screen.findByText('Анна Петрова · anna@example.com')).toBeInTheDocument()
    expect(calls.find((call) => call.key === 'POST /invitations/accept')?.body).toEqual({
      token: 'secret-token',
      password: 'abcdefgh1',
      password_confirmation: 'abcdefgh1',
    })
  })

  it('по недействительной ссылке показывает «Ссылка устарела» и просит новое приглашение', async () => {
    mockBackend({
      'POST /invitations/preview': () =>
        jsonResponse({ detail: 'Invitation is no longer valid' }, 410),
    })
    renderApp('/invitation#token=used')
    expect(await screen.findByRole('heading', { name: 'Ссылка устарела' })).toBeInTheDocument()
    expect(screen.getByText(/Попросите администратора отправить новое приглашение/)).toBeVisible()
  })
})

describe('восстановление пароля', () => {
  it('показывает одинаковый ответ, подсказку про «Спам» и блокирует повтор на 60 с', async () => {
    mockBackend({
      'POST /password-reset/request': () =>
        jsonResponse({ detail: 'If the account exists...' }, 202),
    })
    renderApp('/forgot-password')
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/Email/), 'anna@example.com')
    await user.click(screen.getByRole('button', { name: 'Отправить ссылку' }))

    expect(await screen.findByText(/Проверьте папку «Спам»/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Отправить ещё раз через (60|59) с/ })).toBeDisabled()
  })

  it('берёт оставшееся время повтора из ответа 429', async () => {
    mockBackend({
      'POST /password-reset/request': () =>
        jsonResponse({ detail: 'Too many', retry_after_seconds: 42 }, 429),
    })
    renderApp('/forgot-password')
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/Email/), 'anna@example.com')
    await user.click(screen.getByRole('button', { name: 'Отправить ссылку' }))

    expect(
      await screen.findByRole('button', { name: /Отправить ещё раз через (42|41) с/ }),
    ).toBeDisabled()
  })
})

describe('сотрудники', () => {
  it('показывает «Этот email уже есть в системе» у поля и не закрывает форму', async () => {
    mockBackend({
      'GET /auth/me': () => jsonResponse({ subject: ADMIN_SUBJECT }),
      'GET /admin/managers': () => jsonResponse({ managers: [] }),
      'POST /admin/managers': () =>
        jsonResponse(
          { detail: 'A manager with this email already exists', field: 'email' },
          422,
        ),
    })
    renderApp('/employees')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Добавить менеджера' }))
    await user.type(await screen.findByLabelText(/Имя и фамилия/), 'Анна Петрова')
    await user.type(screen.getByLabelText(/Email/), 'anna@example.com')
    await user.click(screen.getByRole('button', { name: 'Добавить' }))

    expect(await screen.findByText('Этот email уже есть в системе')).toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Новый менеджер' })).toBeInTheDocument()
  })

  it('исправляет email ожидающего менеджера повтором приглашения', async () => {
    const calls = mockBackend({
      'GET /auth/me': () => jsonResponse({ subject: ADMIN_SUBJECT }),
      'GET /admin/managers': () => jsonResponse({ managers: [PENDING_MANAGER] }),
      'POST /admin/managers/7/invitation': () =>
        jsonResponse({
          manager: { ...PENDING_MANAGER, email: 'ivan.s@example.com' },
          delivery: { status: 'sent' },
        }),
    })
    renderApp('/employees')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Повторить приглашение' }))
    const email = await screen.findByLabelText(/Email/)
    await user.clear(email)
    await user.type(email, 'ivan.s@example.com')
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    expect(await screen.findByText('Приглашение отправлено на ivan.s@example.com.')).toBeVisible()
    expect(calls.find((call) => call.key === 'POST /admin/managers/7/invitation')?.body).toEqual({
      email: 'ivan.s@example.com',
    })
  })

  it('при сбое SMTP сообщает, что менеджер сохранён без письма', async () => {
    mockBackend({
      'GET /auth/me': () => jsonResponse({ subject: ADMIN_SUBJECT }),
      'GET /admin/managers': () => jsonResponse({ managers: [] }),
      'POST /admin/managers': () =>
        jsonResponse(
          {
            detail: 'Invitation email could not be delivered',
            manager: PENDING_MANAGER,
            delivery: { status: 'failed' },
          },
          502,
        ),
    })
    renderApp('/employees')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Добавить менеджера' }))
    await user.type(await screen.findByLabelText(/Имя и фамилия/), 'Иван Сидоров')
    await user.type(screen.getByLabelText(/Email/), 'ivan@example.com')
    await user.click(screen.getByRole('button', { name: 'Добавить' }))

    expect(await screen.findByText(/сохранён, но письмо на ivan@example.com не отправлено/)).toBeVisible()
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Новый менеджер' })).not.toBeInTheDocument(),
    )
  })
})
