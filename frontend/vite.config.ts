import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const backendProxy = {
  '/health': 'http://127.0.0.1:8000',
}

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: backendProxy,
  },
  preview: {
    proxy: backendProxy,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
