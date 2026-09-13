import {
  Cpu,
  Database,
  Target,
  GitBranch,
  ListOrdered,
} from 'lucide-react'
import { ApiError, getModelInfo } from '@/lib/api'
import { mapModelInfo } from '@/lib/mappers'
import { PageHeader } from '@/components/page-header'
import { LastUpdated } from '@/components/last-updated'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { ApiUnavailable } from '@/components/api-unavailable'

export const dynamic = 'force-dynamic'

export default async function ModelInfoPage() {
  try {
    const meta = await getModelInfo()
    const info = mapModelInfo(meta)

    const specs = [
      { icon: GitBranch, label: 'Version', value: info.version },
      { icon: Cpu, label: 'Algorithm', value: 'Random Forest' },
      {
        icon: Database,
        label: 'Eval. Records',
        value:
          info.records_trained === null
            ? '—'
            : info.records_trained.toLocaleString('en-IN'),
      },
    ]

    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Model Information"
          subtitle="Transparency into the predictive delay-risk model."
          actions={<LastUpdated timestamp={new Date().toISOString()} />}
        />

        <section>
          <Card>
            <CardContent className="flex flex-col gap-5 p-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-4">
                <div className="flex size-12 items-center justify-center rounded-lg bg-primary/15 text-primary ring-1 ring-inset ring-primary/25">
                  <Cpu className="size-6" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-foreground">{info.model_name}</h2>
                  <p className="text-sm text-muted-foreground">Random Forest classifier</p>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 sm:gap-6">
                {specs.map((s) => (
                  <div key={s.label}>
                    <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                      {s.label}
                    </p>
                    <p className="mt-0.5 break-words text-sm font-medium text-foreground">{s.value}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </section>

        {info.metrics.length > 0 ? (
          <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {info.metrics.map((m) => (
              <Card key={m.label} className="p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {m.label}
                </p>
                <p className="mt-2 text-3xl font-semibold tabular-nums text-foreground">
                  {m.value}
                </p>
              </Card>
            ))}
          </section>
        ) : null}

        <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-1">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="size-4 text-primary" />
                Prediction Target
              </CardTitle>
              <CardDescription>What the model estimates</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <p className="text-sm leading-relaxed text-foreground">{info.target}</p>
              <div className="rounded-md border border-border bg-background/40 p-3">
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  Training Scope
                </p>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  {info.training_scope}
                </p>
              </div>
              <div className="rounded-md border border-border bg-background/40 p-3">
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  Validation / Test
                </p>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  {info.validation_scope} · {info.test_scope}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ListOrdered className="size-4 text-primary" />
                Model Features
              </CardTitle>
              <CardDescription>Inputs used to generate each prediction</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {info.features.map((f, i) => (
                <div
                  key={f.name}
                  className="flex gap-3 rounded-md border border-border bg-background/40 p-3"
                >
                  <span className="flex size-6 shrink-0 items-center justify-center rounded bg-muted text-xs font-medium tabular-nums text-muted-foreground">
                    {i + 1}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-foreground">{f.name}</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                      {f.description}
                    </p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </section>

        <section>
          <Card>
            <CardContent className="p-4">
              <p className="text-xs leading-relaxed text-muted-foreground">
                <span className="font-medium text-foreground">Note:</span> The model estimates
                the probability of next-month additional delay. Predictions are
                decision-support estimates and should be interpreted alongside on-ground project
                review. Drivers are rule-based warning flags, not causal explanations.
              </p>
            </CardContent>
          </Card>
        </section>
      </div>
    )
  } catch (error) {
    const message =
      error instanceof ApiError ? error.message : 'PAIMANA API is currently unavailable.'
    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Model Information"
          subtitle="Transparency into the predictive delay-risk model."
        />
        <ApiUnavailable message={message} />
      </div>
    )
  }
}
