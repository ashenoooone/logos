import { MantineProvider } from '@mantine/core'
import { RouterProvider } from '@tanstack/react-router'

import { router } from './router'
import { appTheme } from './theme'

export function App() {
  return (
    <MantineProvider theme={appTheme}>
      <RouterProvider router={router} />
    </MantineProvider>
  )
}
