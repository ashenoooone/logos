import {
  createRootRoute,
  createRoute,
  createRouter,
  type RouterHistory,
} from '@tanstack/react-router'

import { AdminLoginPage } from '@/pages/admin-login/admin-login-page'
import { EmployeesPage } from '@/pages/employees/employees-page'
import { ForgotPasswordPage } from '@/pages/forgot-password/forgot-password-page'
import { HomePage } from '@/pages/home/home-page'
import { InvitationPage } from '@/pages/invitation/invitation-page'
import { LoginPage } from '@/pages/login/login-page'
import { NotFoundPage } from '@/pages/not-found/not-found-page'
import { PasswordResetPage } from '@/pages/password-reset/password-reset-page'

import { AdministratorLayout } from './layouts/administrator-layout'
import { AnonymousLayout } from './layouts/anonymous-layout'
import { AuthenticatedLayout } from './layouts/authenticated-layout'
import { RootLayout } from './layouts/root-layout'

// SPA-пути не должны начинаться с API-префиксов из vite.config.ts
// (/health, /auth, /admin, /invitations, /password-reset/).

const rootRoute = createRootRoute({
  component: RootLayout,
  notFoundComponent: NotFoundPage,
})

const anonymousRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'anonymous',
  component: AnonymousLayout,
})

const authenticatedRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'authenticated',
  component: AuthenticatedLayout,
})

const administratorRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  id: 'administrator',
  component: AdministratorLayout,
})

const routeTree = rootRoute.addChildren([
  anonymousRoute.addChildren([
    createRoute({ getParentRoute: () => anonymousRoute, path: '/login', component: LoginPage }),
    createRoute({
      getParentRoute: () => anonymousRoute,
      path: '/login/admin',
      component: AdminLoginPage,
    }),
    createRoute({
      getParentRoute: () => anonymousRoute,
      path: '/forgot-password',
      component: ForgotPasswordPage,
    }),
  ]),
  authenticatedRoute.addChildren([
    createRoute({ getParentRoute: () => authenticatedRoute, path: '/', component: HomePage }),
    administratorRoute.addChildren([
      createRoute({
        getParentRoute: () => administratorRoute,
        path: '/employees',
        component: EmployeesPage,
      }),
    ]),
  ]),
  // Ссылки из писем открываются в любом состоянии сессии: успех создаёт новую сессию.
  createRoute({ getParentRoute: () => rootRoute, path: '/invitation', component: InvitationPage }),
  createRoute({
    getParentRoute: () => rootRoute,
    path: '/password-reset',
    component: PasswordResetPage,
  }),
])

export function createAppRouter(history?: RouterHistory) {
  return createRouter({ routeTree, history })
}

export const router = createAppRouter()

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
