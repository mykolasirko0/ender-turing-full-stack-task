import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Navigate } from "@tanstack/react-router"

import { MetricsService, type UserMetrics } from "@/client"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import usePermissions from "@/hooks/usePermissions"
import { requirePermission } from "@/lib/permissions"
import { ROLE_LABELS, ROLES } from "@/lib/roles"

export const Route = createFileRoute("/_layout/metrics")({
  component: Metrics,
  beforeLoad: () => requirePermission("metrics:read"),
  head: () => ({
    meta: [
      {
        title: "Metrics - FastAPI Template",
      },
    ],
  }),
})

type Stat = { label: string; value: number }

const toStats = (metrics: UserMetrics): Stat[] => [
  { label: "Total users", value: metrics.total_users },
  { label: "Active users", value: metrics.active_users },
  ...ROLES.map((role) => ({
    label: `${ROLE_LABELS[role]}s`,
    value: metrics.users_by_role[role] ?? 0,
  })),
]

const STAT_COUNT = 2 + ROLES.length

function StatCard({ label, value }: Stat) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-3xl tabular-nums">{value}</CardTitle>
      </CardHeader>
    </Card>
  )
}

function PendingStats() {
  return Array.from({ length: STAT_COUNT }, (_, index) => (
    <Card key={index}>
      <CardContent className="flex flex-col gap-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-12" />
      </CardContent>
    </Card>
  ))
}

function Metrics() {
  const { can, isLoaded } = usePermissions()
  const allowed = can("metrics:read")

  const { data, isError } = useQuery({
    queryKey: ["metrics"],
    queryFn: async () => (await MetricsService.readMetrics()).data,
    enabled: allowed,
  })

  // beforeLoad guards navigation; this covers losing access while on the page.
  if (isLoaded && !allowed) {
    return <Navigate to="/" />
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Metrics</h1>
        <p className="text-muted-foreground">User counts across the system</p>
      </div>
      {isError ? (
        <p className="text-destructive">Could not load metrics.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {data ? (
            toStats(data).map((stat) => <StatCard key={stat.label} {...stat} />)
          ) : (
            <PendingStats />
          )}
        </div>
      )}
    </div>
  )
}
