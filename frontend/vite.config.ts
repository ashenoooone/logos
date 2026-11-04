import { fileURLToPath } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const backendProxy = {
  // Префиксы API; SPA-маршруты не должны с ними пересекаться (/password-reset без слеша — страница).
  '/health': 'http://127.0.0.1:8000',
  '/auth': 'http://127.0.0.1:8000',
  '/admin': 'http://127.0.0.1:8000',
  '/invitations': 'http://127.0.0.1:8000',
  '/password-reset/': 'http://127.0.0.1:8000',
}

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: backendProxy,
  },
  preview: {
    proxy: backendProxy,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/app/test/setup.ts'],
  },
})
