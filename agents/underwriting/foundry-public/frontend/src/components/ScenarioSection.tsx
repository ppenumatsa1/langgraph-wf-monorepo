type Scenario = 'happy' | 'retry' | 'crash-medical'

type Props = {
  scenario: Scenario
  onChange: (scenario: Scenario) => void
}

export function ScenarioSection({ scenario, onChange }: Props) {
  return (
    <section className="card scenario-card">
      <h2>Scenario</h2>
      <label className="field">
        Use case
        <select
          data-testid="scenario-select"
          value={scenario}
          onChange={(e) => onChange(e.target.value as Scenario)}
        >
          <option value="happy">Happy path</option>
          <option value="retry">Retry once (FAIL_RISK_ONCE)</option>
          <option value="crash-medical">Crash after medical check</option>
        </select>
      </label>
    </section>
  )
}
