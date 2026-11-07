import { createContext, useContext } from 'react'

import type { Subject } from '../api/session'

export interface SessionContextValue {
  subject: Subject | null
  /** Вызывать после входа, принятия приглашения и выхода. */
  setSubject: (subject: Subject | null) => void
}

export const SessionContext = createContext<SessionContextValue | null>(null)

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext)
  if (!value) {
    throw new Error('useSession вызван вне SessionProvider')
  }
  return value
}
