import {
  createRootRoute,
  createRoute,
  createRouter,
  type RouterHistory,
} from '@tanstack/react-router'

import { AdminLoginPage } from '@/pages/admin-login/admin-login-page'
import { ChannelsPage } from '@/pages/channels/channels-page'
import { EmployeesPage } from '@/pages/employees/employees-page'
import { EmailConfirmationPage } from '@/pages/email-confirmation/email-confirmation-page'
import { ForgotPasswordPage } from '@/pages/forgot-password/forgot-password-page'
import { HomePage } from '@/pages/home/home-page'
import { InboxPage } from '@/pages/inbox/inbox-page'
import { InvitationPage } from '@/pages/invitation/invitation-page'
import { LoginPage } from '@/pages/login/login-page'
import { NotFoundPage } from '@/pages/not-found/not-found-page'
import { PasswordResetPage } from '@/pages/password-reset/password-reset-page'
import { ProfilePage } from '@/pages/profile/profile-page'

import { AdministratorLayout } from './layouts/administrator-layout'
import { AnonymousLayout } from './layouts/anonymous-layout'
import { AuthenticatedLayout } from './layouts/authenticated-layout'
import { ManagerLayout } from './layouts/manager-layout'
import { RootLayout } from './layouts/root-layout'

// SPA-пути не должны начинаться с API-префиксов из vite.config.ts
// (/health, /auth, /admin, /invitations, /password-reset/, /account, /conversations, /messages).

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

const managerRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  id: 'manager',
  component: ManagerLayout,
})

const routeTree = rootRoute.addChildren([
  anonymousRoute.addChildren([
    createRoute({ getParentRoute: () => anonymousRoute, path: '/login', component: LoginPage }),
    createRoute({
      getParentRoute: () => anonymousRoute,
      path: '/login/admin',
      component: AdminLoginPage,
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
      createRoute({
        getParentRoute: () => administratorRoute,
        path: '/channels',
        component: ChannelsPage,
      }),
    ]),
    managerRoute.addChildren([
      createRoute({ getParentRoute: () => managerRoute, path: '/inbox', component: InboxPage }),
      createRoute({ getParentRoute: () => managerRoute, path: '/profile', component: ProfilePage }),
    ]),
  ]),
  // Восстановление доступно и из профиля («Забыли пароль?»), поэтому без guard анонима.
  createRoute({
    getParentRoute: () => rootRoute,
    path: '/forgot-password',
    component: ForgotPasswordPage,
  }),
  // Ссылки из писем открываются в любом состоянии сессии: успех создаёт новую сессию.
  createRoute({ getParentRoute: () => rootRoute, path: '/invitation', component: InvitationPage }),
  createRoute({
    getParentRoute: () => rootRoute,
    path: '/password-reset',
    component: PasswordResetPage,
  }),
  createRoute({
    getParentRoute: () => rootRoute,
    path: '/email-confirmation',
    component: EmailConfirmationPage,
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
