import { screen, waitFor } from '@testing-library/react'
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
    expect(await screen.findByRole('heading', { name: 'Здравствуйте, Анна' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Сотрудники' })).not.toBeInTheDocument()
  })
})

describe('вход менеджера', () => {
  async function requestCode(user = userEvent.setup()) {
    await user.type(await screen.findByLabelText(/Email/), 'anna@example.com')
    await user.click(screen.getByRole('button', { name: 'Получить код' }))
    return user
  }

  it('даёт нейтральный ответ и 60-секундную паузу при запросе кода', async () => {
    mockBackend({
      'POST /auth/manager/otp/request': () => jsonResponse({ detail: 'If the account exists...' }, 202),
    })
    renderApp('/login')
    await requestCode()
    expect(await screen.findByText(/Если учётная запись существует/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Отправить код ещё раз через/ })).toBeDisabled()
  })

  it('показывает интервал из retry_after_seconds при ограничении запросов', async () => {
    mockBackend({
      'POST /auth/manager/otp/request': () =>
        jsonResponse({ detail: 'Too many', retry_after_seconds: 42 }, 429),
    })
    renderApp('/login')
    await requestCode()
    expect(await screen.findByRole('alert')).toHaveTextContent('через 42 с')
    expect(screen.getByRole('button', { name: 'Получить код' })).toBeDisabled()
  })

  it('сохраняет remember, показывает ошибку кода и завершает сессию штатно', async () => {
    let attempts = 0
    const calls = mockBackend({
      'POST /auth/manager/otp/request': () => jsonResponse({}, 202),
      'POST /auth/manager/otp/verify': () =>
        ++attempts === 1
          ? jsonResponse({ detail: 'Invalid or expired code' }, 401)
          : jsonResponse({ subject: MANAGER_SUBJECT }),
      'POST /auth/logout': () => new Response(null, { status: 204 }),
    })
    renderApp('/login')
    const user = await requestCode()
    await user.type(screen.getByRole('textbox', { name: /Код из письма/ }), '123456')
    await user.click(screen.getByRole('button', { name: 'Подтвердить код' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Неверный или просроченный код')

    await user.click(screen.getByLabelText('Запомнить меня'))
    await user.click(screen.getByRole('button', { name: 'Подтвердить код' }))
    expect(await screen.findByText('anna@example.com')).toBeInTheDocument()
    const verify = calls.filter((call) => call.key === 'POST /auth/manager/otp/verify').at(-1)
    expect(verify?.body).toEqual({ email: 'anna@example.com', code: '123456', remember: true })
    expect(verify?.headers.get('X-CSRF-Token')).toBe(CSRF_TOKEN)
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

    expect(await screen.findByText('anna@example.com')).toBeInTheDocument()
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
