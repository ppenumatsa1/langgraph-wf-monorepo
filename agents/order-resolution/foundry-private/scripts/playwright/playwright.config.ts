import { defineConfig } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:5173";
const artifactsDir = process.env.PLAYWRIGHT_ARTIFACTS_DIR ?? ".artifacts";
const isHostedTarget = baseURL.startsWith("https://");

function readTimeout(name: string, fallback: number): number {
  const value = Number(process.env[name] ?? fallback);
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error(`${name} must be a positive number`);
  }
  return value;
}

const expectTimeout = readTimeout(
  "PLAYWRIGHT_EXPECT_TIMEOUT_MS",
  isHostedTarget ? 60_000 : 10_000,
);
const testTimeout = readTimeout(
  "PLAYWRIGHT_TEST_TIMEOUT_MS",
  isHostedTarget ? 120_000 : 45_000,
);

export default defineConfig({
  testDir: "./tests",
  outputDir: `${artifactsDir}/test-results`,
  timeout: testTimeout,
  expect: {
    timeout: expectTimeout,
  },
  use: {
    baseURL,
    headless: true,
  },
  reporter: [["list"], ["html", { outputFolder: `${artifactsDir}/playwright-report` }]],
});
