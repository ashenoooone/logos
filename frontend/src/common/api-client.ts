// Единый клиент JSON-API бэкенда (same-origin, сессия в HttpOnly-cookie).
// Каждый POST несёт X-CSRF-Token = cookie logos_csrf; токен берётся через GET /auth/csrf,
// если cookie ещё нет. Origin браузер подставляет сам.

const CSRF_COOKIE = 'logos_csrf'
const CSRF_ENDPOINT = '/auth/csrf'

export interface ApiResponse<T = unknown> {
  status: number
  data: T
}

/** Тело прикладной ошибки бэкенда: `{"detail", "field"?, ...}`. */
export interface ApiErrorBody {
  detail?: string
  field?: string
  attempts_remaining?: number
  retry_after_seconds?: number
}

function readCookie(name: string): string | null {
  for (const part of document.cookie.split(';')) {
    const [key, ...rest] = part.trim().split('=')
    if (key === name) {
      return decodeURIComponent(rest.join('='))
    }
  }
  return null
}

async function csrfToken(signal?: AbortSignal): Promise<string> {
  const existing = readCookie(CSRF_COOKIE)
  if (existing) {
    return existing
  }
  const response = await apiGet<{ csrf_token?: string }>(CSRF_ENDPOINT, signal)
  const token = response.data?.csrf_token
  if (response.status !== 200 || !token) {
    throw new Error(`CSRF bootstrap failed: HTTP ${response.status}`)
  }
  return token
}

async function parse<T>(response: Response): Promise<ApiResponse<T>> {
  let data: unknown = null
  if (response.headers.get('content-type')?.includes('application/json')) {
    try {
      data = await response.json()
    } catch {
      data = null
    }
  }
  return { status: response.status, data: data as T }
}

export async function apiGet<T = unknown>(
  path: string,
  signal?: AbortSignal,
): Promise<ApiResponse<T>> {
  const response = await fetch(path, {
    method: 'GET',
    headers: { accept: 'application/json' },
    credentials: 'same-origin',
    cache: 'no-store',
    signal,
  })
  return parse<T>(response)
}

/** Сетевая ошибка и отмена пробрасываются исключением; HTTP-ошибки — в `status`. */
export async function apiPost<T = unknown>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<ApiResponse<T>> {
  const token = await csrfToken(signal)
  const response = await fetch(path, {
    method: 'POST',
    headers: {
      accept: 'application/json',
      'content-type': 'application/json',
      'X-CSRF-Token': token,
    },
    body: JSON.stringify(body ?? {}),
    credentials: 'same-origin',
    cache: 'no-store',
    signal,
  })
  return parse<T>(response)
}

/** POST с сырым телом (файл); CSRF и обработка ошибок как у `apiPost`. */
export async function apiUpload<T = unknown>(path: string, file: Blob): Promise<ApiResponse<T>> {
  const token = await csrfToken()
  const response = await fetch(path, {
    method: 'POST',
    headers: {
      accept: 'application/json',
      'content-type': 'application/octet-stream',
      'X-CSRF-Token': token,
    },
    body: file,
    credentials: 'same-origin',
    cache: 'no-store',
  })
  return parse<T>(response)
}

/** Текст для непредусмотренного исхода: `status` не задан — нет связи с сервисом. */
export function failureMessage(status?: number): string {
  return status === undefined
    ? 'Не удалось подключиться к сервису. Проверьте соединение и повторите попытку.'
    : `Сервис вернул HTTP ${status}. Повторите попытку позже.`
}
