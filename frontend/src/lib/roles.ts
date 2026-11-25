import type { Role } from "@/client"

// Record<Role, …> makes this fail to compile if the backend adds a role.
export const ROLE_LABELS: Record<Role, string> = {
  admin: "Admin",
  manager: "Manager",
  member: "Member",
}

// Ordered most to least privileged; tuple form is what z.enum() needs.
export const ROLES = [
  "admin",
  "manager",
  "member",
] as const satisfies readonly Role[]

export const DEFAULT_ROLE: Role = "member"

export const isRole = (value: string): value is Role =>
  (ROLES as readonly string[]).includes(value)
