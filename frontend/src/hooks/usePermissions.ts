import { useCallback } from "react"

import type { Permission } from "@/client"
import { hasPermission } from "@/lib/permissions"
import useAuth from "./useAuth"

const usePermissions = () => {
  const { user } = useAuth()

  const can = useCallback(
    (permission: Permission) => hasPermission(user, permission),
    [user],
  )

  // `user` is undefined while /users/me is loading: callers that redirect on
  // a missing permission must wait for it, or they'd redirect every reload.
  return { user, can, isLoaded: user != null }
}

export default usePermissions
