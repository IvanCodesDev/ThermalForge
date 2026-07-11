import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const apiProxyTarget =
  process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  assetsInclude: ['**/*.stl'],
  server: {
    fs: {
      allow: ['..'],
    },
    proxy: {
      '/health': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
      '/v1': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
  },
})
