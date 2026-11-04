import { Outlet } from '@tanstack/react-router'

import { RequireSession } from '@/modules/session'

export function AnonymousLayout() {
  return (
    <RequireSession access="anonymous">
      <Outlet />
    </RequireSession>
  )
}
