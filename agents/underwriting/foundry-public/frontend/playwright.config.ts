import { defineConfig } from '@playwright/test'

const localBackendPort = process.env.E2E_BACKEND_HOST_PORT ?? '8000'
const localApiBase = `http://127.0.0.1:${localBackendPort}`
const deployedRun = Boolean(process.env.PLAYWRIGHT_BASE_URL)

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  timeout: deployedRun ? 600000 : 120000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:4175',
    trace: 'on-first-retry',
  },
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: 'npm run dev -- --host 127.0.0.1 --port 4175',
        env: {
          ...process.env,
          VITE_PROXY_TARGET: localApiBase,
        },
        port: 4175,
        reuseExistingServer: true,
        timeout: 120000,
      },
})
