import React from "react";
import ReactDOM from "react-dom/client";
import { CopilotKit } from "@copilotkit/react-core/v2";
import "@copilotkit/react-core/v2/styles.css";

import App from "./App";
import { orderResolutionCopilotRuntime } from "./copilot";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <CopilotKit
      runtimeUrl={orderResolutionCopilotRuntime.runtimeUrl}
      credentials={orderResolutionCopilotRuntime.credentials}
      useSingleEndpoint={false}
      enableInspector={false}
    >
      <App />
    </CopilotKit>
  </React.StrictMode>,
);
