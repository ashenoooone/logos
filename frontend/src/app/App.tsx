import { MantineProvider } from '@mantine/core'
import { RouterProvider } from '@tanstack/react-router'

import { appTheme } from './config/theme'
import { router } from './router'

export function App() {
  return (
    <MantineProvider theme={appTheme}>
      <RouterProvider router={router} />
    </MantineProvider>
  )
}
