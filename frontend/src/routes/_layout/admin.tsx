import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Navigate } from "@tanstack/react-router"
import { Suspense } from "react"

import { type UserPublic, UsersService } from "@/client"
import AddUser from "@/components/Admin/AddUser"
import { columns, type UserTableData } from "@/components/Admin/columns"
import { DataTable } from "@/components/Common/DataTable"
import PendingUsers from "@/components/Pending/PendingUsers"
import usePermissions from "@/hooks/usePermissions"
import { requirePermission } from "@/lib/permissions"

function getUsersQueryOptions() {
  return {
    queryFn: async () =>
      (await UsersService.readUsers({ query: { skip: 0, limit: 100 } })).data,
    queryKey: ["users"],
  }
}

export const Route = createFileRoute("/_layout/admin")({
  component: Admin,
  beforeLoad: () => requirePermission("users:read"),
  head: () => ({
    meta: [
      {
        title: "Admin - FastAPI Template",
      },
    ],
  }),
})

function UsersTableContent({ canManage }: { canManage: boolean }) {
  const { user: currentUser } = usePermissions()
  const { data: users } = useSuspenseQuery(getUsersQueryOptions())

  const tableData: UserTableData[] = users.data.map((user: UserPublic) => ({
    ...user,
    isCurrentUser: currentUser?.id === user.id,
  }))

  // Read-only for users:read without users:manage (managers): no row actions.
  const visibleColumns = canManage
    ? columns
    : columns.filter((column) => column.id !== "actions")

  return <DataTable columns={visibleColumns} data={tableData} />
}

function UsersTable({ canManage }: { canManage: boolean }) {
  return (
    <Suspense fallback={<PendingUsers />}>
      <UsersTableContent canManage={canManage} />
    </Suspense>
  )
}

function Admin() {
  const { can, isLoaded } = usePermissions()

  // beforeLoad guards navigation; this covers losing access while on the
  // page (e.g. currentUser refetched after a 403).
  if (isLoaded && !can("users:read")) {
    return <Navigate to="/" />
  }

  const canManage = can("users:manage")

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Users</h1>
          <p className="text-muted-foreground">
            {canManage
              ? "Manage user accounts and permissions"
              : "View user accounts (read-only)"}
          </p>
        </div>
        {canManage && <AddUser />}
      </div>
      <UsersTable canManage={canManage} />
    </div>
  )
}
