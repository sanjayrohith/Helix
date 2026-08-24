import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
  test: {
    // Explicit imports (describe/it/expect from 'vitest') rather than
    // globals: true - one fewer ambient-type declaration to keep in sync
    // with tsconfig, and a test file's dependencies are visible at a glance.
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
