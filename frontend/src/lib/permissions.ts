import { redirect } from "@tanstack/react-router"
import { AxiosError } from "axios"

import { type Permission, type UserMe, UsersService } from "@/client"

// The backend is the source of truth: /users/me returns the permissions
// granted by the user's role. The frontend only mirrors them for UX.
export const hasPermission = (
  user: Pick<UserMe, "permissions"> | null | undefined,
  permission: Permission,
): boolean => user?.permissions.includes(permission) ?? false

/**
 * Route `beforeLoad` guard. Fetches the current user fresh (so a role change
 * is picked up on navigation) and redirects home without the permission.
 */
export const requirePermission = async (permission: Permission) => {
  let user: UserMe
  try {
    user = (await UsersService.readUserMe()).data
  } catch (error) {
    // Runs outside React Query, so the global 401 handler doesn't see it.
    if (error instanceof AxiosError && error.response?.status === 401) {
      localStorage.removeItem("access_token")
      throw redirect({ to: "/login" })
    }
    throw error
  }
  if (!hasPermission(user, permission)) {
    throw redirect({ to: "/" })
  }
}
