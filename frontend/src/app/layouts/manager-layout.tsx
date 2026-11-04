import { Outlet } from '@tanstack/react-router'

import { RequireSession } from '@/modules/session'

export function ManagerLayout() {
  return (
    <RequireSession access="manager">
      <Outlet />
    </RequireSession>
  )
}
