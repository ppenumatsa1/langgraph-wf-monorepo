# Frontend

React/Vite renders the order-resolution UI. Production uses non-root Nginx on
port 5173. The `/api` location proxies to the internal backend with SSE-safe
buffering and timeout settings. Browser code never receives an Azure resource
endpoint or credential.

```bash
npm ci
npm run build
npm run test:e2e
```
