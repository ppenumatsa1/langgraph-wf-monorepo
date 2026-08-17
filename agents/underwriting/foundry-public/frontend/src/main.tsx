import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { CopilotKit } from '@copilotkit/react-core/v2'
import '@copilotkit/react-core/v2/styles.css'
import './index.css'
import App from './App.tsx'
import { underwritingCopilotRuntime } from './copilot.ts'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <CopilotKit
      runtimeUrl={underwritingCopilotRuntime.runtimeUrl}
      credentials={underwritingCopilotRuntime.credentials}
      useSingleEndpoint={false}
    >
      <App />
    </CopilotKit>
  </StrictMode>,
)
