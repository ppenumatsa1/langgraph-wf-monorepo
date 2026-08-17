import type { UnderwritingApplication } from '../api'

type Props = {
  application: UnderwritingApplication
  onChange: (next: UnderwritingApplication) => void
}

export function ApplicationSection({ application, onChange }: Props) {
  const fields: Array<{
    key: keyof UnderwritingApplication
    label: string
    type?: 'text' | 'number'
    step?: string
  }> = [
    { key: 'application_id', label: 'Application ID' },
    { key: 'applicant_name', label: 'Applicant name' },
    { key: 'age', label: 'Age', type: 'number', step: '1' },
    { key: 'income', label: 'Income', type: 'number', step: '1000' },
    { key: 'requested_coverage', label: 'Requested coverage', type: 'number', step: '1000' },
    { key: 'health_disclosures', label: 'Health disclosures' },
    { key: 'driving_history', label: 'Driving history' },
    { key: 'credit_score', label: 'Credit score', type: 'number', step: '1' },
  ]

  return (
    <section className="card application-card form-grid">
      <h2>Application Input</h2>
      {fields.map(({ key, label, type = 'text', step }) => (
        <label key={key} className="field">
          {label}
          <input
            data-testid={`field-${key}`}
            type={type}
            inputMode={type === 'number' ? 'numeric' : undefined}
            step={step}
            value={String(application[key])}
            onChange={(e) =>
              onChange({
                ...application,
                [key]:
                  key === 'age' || key === 'credit_score' || key === 'income' || key === 'requested_coverage'
                    ? Number(e.target.value)
                    : e.target.value,
              })
            }
          />
        </label>
      ))}
    </section>
  )
}
