import { MantineProvider } from '@mantine/core'
import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { useState } from 'react'

import { SessionProvider } from '@/modules/session'

import { createQueryClient } from './config/query-client'
import { appTheme, cssVariablesResolver } from './config/theme'
import { router } from './router'

export function App() {
  const [queryClient] = useState(createQueryClient)

  return (
    <QueryClientProvider client={queryClient}>
      <MantineProvider theme={appTheme} cssVariablesResolver={cssVariablesResolver}>
        <SessionProvider>
          <RouterProvider router={router} />
        </SessionProvider>
      </MantineProvider>
    </QueryClientProvider>
  )
}
