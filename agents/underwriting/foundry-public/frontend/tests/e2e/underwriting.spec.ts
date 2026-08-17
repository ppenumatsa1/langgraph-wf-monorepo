import { expect, test, type Page } from '@playwright/test'

import { scoreRubric, type RubricResultMap } from './rubric'

const workflowTimeout = process.env.PLAYWRIGHT_BASE_URL ? 120_000 : 30_000

async function startScenario(page: Page, scenario: 'happy' | 'retry' | 'crash-medical') {
  const previousRunText = await page.getByTestId('run-id').innerText()
  await page.getByRole('button', { name: 'New underwriting run' }).click()
  await page
    .getByTestId('field-application_id')
    .fill(`app-e2e-${scenario}-${Date.now()}-${Math.floor(Math.random() * 1000)}`)
  await page.getByTestId('scenario-select').selectOption(scenario)
  await page.getByTestId('start-run').click()
  await expect
    .poll(async () => page.getByTestId('run-id').innerText())
    .not.toBe(previousRunText)
}

test('underwriting rubric scenarios', async ({ page }) => {
  const rubric: RubricResultMap = {
    'happy-path-decision': false,
    'retry-behavior': false,
    'crash-state': false,
    'resume-from-checkpoint': false,
    'fanin-state': false,
    'checkpoint-listing': false,
    'idempotency-skip': false,
    'observability-fields': false,
  }

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Underwriting Workflow Runs' })).toBeVisible()
  await expect.poll(async () => (await page.request.get('/backend-health')).status()).toBe(200)

  await startScenario(page, 'happy')
  await expect(page.getByTestId('run-status')).toContainText('COMPLETED', {
    timeout: workflowTimeout,
  })
  await expect(page.getByTestId('run-outputs')).toContainText('decision')
  rubric['happy-path-decision'] = true
  const happyRunId = (await page.getByTestId('run-id').innerText()).replace('Run ID', '').trim()
  const assistantInput = page.getByPlaceholder('Ask about this run')
  await assistantInput.fill('What is the status?')
  await assistantInput.press('Enter')
  await expect(page.getByText(`Run ${happyRunId} is COMPLETED.`)).toBeVisible({
    timeout: workflowTimeout,
  })

  const fanInText = await page.getByTestId('fanin-completed-checks').innerText()
  rubric['fanin-state'] =
    fanInText.includes('risk') &&
    fanInText.includes('credit') &&
    fanInText.includes('medical') &&
    fanInText.includes('driving')

  const checkpointCountText = await page.getByTestId('checkpoint-count').innerText()
  const checkpointCount = Number((checkpointCountText.match(/\d+/) || ['0'])[0])
  rubric['checkpoint-listing'] = checkpointCount > 0
  const chronologicalEvents = JSON.parse((await page.getByTestId('events-json').textContent()) ?? '[]') as Array<{
    created_at: string
  }>
  expect(chronologicalEvents.map((event) => event.created_at)).toEqual(
    [...chronologicalEvents.map((event) => event.created_at)].sort(),
  )

  await startScenario(page, 'retry')
  await expect(page.getByTestId('run-status')).toContainText('COMPLETED', {
    timeout: workflowTimeout,
  })
  const retryText = await page.getByTestId('retry-event-count').innerText()
  const retryCount = Number((retryText.match(/\d+/) || ['0'])[0])
  rubric['retry-behavior'] = retryCount > 0

  await page.getByTestId('history-search').fill(happyRunId)
  await expect(page.getByTestId(`history-run-${happyRunId}`)).toBeVisible()
  await page.getByTestId(`history-run-${happyRunId}`).click()
  await expect(page.getByTestId('run-id')).toContainText(happyRunId)
  await page.getByTestId('history-search').fill('')

  await startScenario(page, 'crash-medical')
  await expect(page.getByTestId('run-status')).toContainText('CRASHED', {
    timeout: workflowTimeout,
  })
  rubric['crash-state'] = true

  await page.getByTestId('resume-run').click()
  await expect
    .poll(async () => page.getByTestId('run-status').innerText(), { timeout: workflowTimeout })
    .toContain('COMPLETED')
  rubric['resume-from-checkpoint'] = true

  const idempotencyText = await page.getByTestId('idempotency-skip-count').innerText()
  const idempotencyCount = Number((idempotencyText.match(/\d+/) || ['0'])[0])
  rubric['idempotency-skip'] = idempotencyCount > 0

  const eventsJson = (await page.getByTestId('events-json').textContent()) ?? ''
  rubric['observability-fields'] =
    eventsJson.includes('workflow_run_id') && eventsJson.includes('executor_name')

  const score = scoreRubric(rubric)
  expect(score.failed, score.failed.join('\n')).toEqual([])
  expect(score.passed).toBe(score.total)
})
