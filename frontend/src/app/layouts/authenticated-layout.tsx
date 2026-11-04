import { Box, Divider } from '@mantine/core'
import { Outlet } from '@tanstack/react-router'

import { InboxNavLink } from '@/modules/inbox'
import { RequireSession, SessionHeader } from '@/modules/session'

export function AuthenticatedLayout() {
  return (
    <RequireSession access="authenticated">
      <Box component="header" bg="white">
        <SessionHeader managerLinks={<InboxNavLink />} />
      </Box>
      <Divider />
      <Outlet />
    </RequireSession>
  )
}
