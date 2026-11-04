import { Navigate } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { useSession } from '../hooks/use-session'

export type SessionAccess = 'anonymous' | 'authenticated' | 'administrator'

/** Guard маршрута: аноним уходит на вход, вошедший — со страниц входа на главную. */
export function RequireSession({
  access,
  children,
}: {
  access: SessionAccess
  children: ReactNode
}) {
  const { subject } = useSession()

  if (access === 'anonymous') {
    return subject ? <Navigate to="/" replace /> : children
  }
  if (!subject) {
    return <Navigate to="/login" replace />
  }
  if (access === 'administrator' && subject.type !== 'administrator') {
    return <Navigate to="/" replace />
  }
  return children
}
