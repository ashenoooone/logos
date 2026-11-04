import { MantineProvider } from '@mantine/core'
import { RouterProvider } from '@tanstack/react-router'

import { SessionProvider } from '@/modules/session'

import { appTheme } from './config/theme'
import { router } from './router'

export function App() {
  return (
    <MantineProvider theme={appTheme}>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </MantineProvider>
  )
}
