import { MantineProvider } from '@mantine/core'
import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router'
import { render } from '@testing-library/react'

import { SessionProvider } from '@/modules/session'

import { createQueryClient } from '../config/query-client'
import { appTheme } from '../config/theme'
import { createAppRouter } from '../router'

export function renderApp(initialEntry = '/') {
  const router = createAppRouter(
    createMemoryHistory({ initialEntries: [initialEntry] }),
  )

  const view = render(
    <QueryClientProvider client={createQueryClient()}>
      <MantineProvider theme={appTheme}>
        <SessionProvider>
          <RouterProvider router={router} />
        </SessionProvider>
      </MantineProvider>
    </QueryClientProvider>,
  )
  return { ...view, router }
}
