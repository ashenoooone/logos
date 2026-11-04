import { Box } from '@mantine/core'
import { Outlet } from '@tanstack/react-router'

import { InboxNavLink } from '@/modules/inbox'
import { RequireSession, SessionHeader } from '@/modules/session'

export function AuthenticatedLayout() {
  return (
    <RequireSession access="authenticated">
      <Box component="header" px={{ base: 0, sm: 'md' }}>
        <Box className="logos-header">
          <SessionHeader managerLinks={<InboxNavLink />} />
        </Box>
      </Box>
      <Outlet />
    </RequireSession>
  )
}
