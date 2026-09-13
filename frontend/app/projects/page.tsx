import { ApiError, getProjects } from '@/lib/api'
import { mapProjectSummary, uniqueSorted } from '@/lib/mappers'
import { PageHeader } from '@/components/page-header'
import { LastUpdated } from '@/components/last-updated'
import { ProjectsExplorer } from '@/components/projects-explorer'
import { ApiUnavailable } from '@/components/api-unavailable'

export const dynamic = 'force-dynamic'

export default async function ProjectsPage() {
  try {
    const payload = await getProjects(2000)
    const projects = payload.projects.map(mapProjectSummary)
    const states = uniqueSorted(projects.map((p) => p.state))
    const agencies = uniqueSorted(projects.map((p) => p.agency))

    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Projects"
          subtitle="Search and filter the full monitored portfolio."
          actions={<LastUpdated timestamp={new Date().toISOString()} />}
        />
        <ProjectsExplorer projects={projects} states={states} agencies={agencies} />
      </div>
    )
  } catch (error) {
    const message =
      error instanceof ApiError ? error.message : 'PAIMANA API is currently unavailable.'
    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Projects"
          subtitle="Search and filter the full monitored portfolio."
        />
        <ApiUnavailable message={message} />
      </div>
    )
  }
}
