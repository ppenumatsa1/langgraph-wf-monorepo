type RuntimeConfig = {
  API_BASE?: string
}

declare global {
  interface Window {
    __APP_CONFIG__?: RuntimeConfig
  }
}

function trimTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, '')
}

export function getInitialApiBase(): string {
  const runtimeBase = window.__APP_CONFIG__?.API_BASE?.trim()
  const viteBase =
    import.meta.env.VITE_API_BASE_URL?.trim() ?? import.meta.env.VITE_API_BASE?.trim()
  return trimTrailingSlashes(runtimeBase || viteBase || '')
}
