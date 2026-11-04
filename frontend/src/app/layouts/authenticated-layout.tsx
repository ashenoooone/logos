import { Box, Divider } from '@mantine/core'
import { Outlet } from '@tanstack/react-router'

import { RequireSession, SessionHeader } from '@/modules/session'

export function AuthenticatedLayout() {
  return (
    <RequireSession access="authenticated">
      <Box component="header" bg="white">
        <SessionHeader />
      </Box>
      <Divider />
      <Outlet />
    </RequireSession>
  )
}
