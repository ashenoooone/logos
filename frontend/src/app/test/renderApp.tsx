import { MantineProvider } from '@mantine/core'
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router'
import { render } from '@testing-library/react'

import { appTheme } from '../config/theme'
import { createAppRouter } from '../router'

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
