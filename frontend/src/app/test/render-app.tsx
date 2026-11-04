import { MantineProvider } from '@mantine/core'
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router'
import { render } from '@testing-library/react'

import { SessionProvider } from '@/modules/session'

import { appTheme } from '../config/theme'
import { createAppRouter } from '../router'

export function renderApp(initialEntry = '/') {
  const router = createAppRouter(
    createMemoryHistory({ initialEntries: [initialEntry] }),
  )

  const view = render(
    <MantineProvider theme={appTheme}>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </MantineProvider>,
  )
  return { ...view, router }
}
