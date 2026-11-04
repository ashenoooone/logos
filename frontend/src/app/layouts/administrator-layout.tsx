import { Outlet } from '@tanstack/react-router'

import { RequireSession } from '@/modules/session'

export function AdministratorLayout() {
  return (
    <RequireSession access="administrator">
      <Outlet />
    </RequireSession>
  )
}
