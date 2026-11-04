import { MantineProvider } from '@mantine/core'
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router'
import { render } from '@testing-library/react'

import { createAppRouter } from '../router'
import { appTheme } from '../theme'

export function renderApp(initialEntry = '/') {
  const router = createAppRouter(
    createMemoryHistory({ initialEntries: [initialEntry] }),
  )

  return render(
    <MantineProvider theme={appTheme}>
      <RouterProvider router={router} />
    </MantineProvider>,
  )
}
