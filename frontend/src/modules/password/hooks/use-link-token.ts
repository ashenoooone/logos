import { useRouter } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

/**
 * Токен одноразовой ссылки из фрагмента `#token=…`. Фрагмент сразу убирается из адреса,
 * чтобы токен не остался в истории браузера и не ушёл дальше при копировании ссылки.
 */
export function useLinkToken(): string | null {
  const router = useRouter()
  const [token] = useState(() => {
    const hash = router.history.location.hash.replace(/^#/, '')
    return new URLSearchParams(hash).get('token') || null
  })

  useEffect(() => {
    const { pathname, search, hash } = router.history.location
    if (hash) {
      router.history.replace(pathname + search)
    }
  }, [router])

  return token
}
