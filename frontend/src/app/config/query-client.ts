import { QueryClient } from '@tanstack/react-query'

/** Поведение запросов как до TanStack Query: без авторетраев и фоновых обновлений. */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
      },
    },
  })
}
