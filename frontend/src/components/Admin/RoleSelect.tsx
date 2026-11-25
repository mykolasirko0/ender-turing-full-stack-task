import type { Role } from "@/client"
import { FormControl } from "@/components/ui/form"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { isRole, ROLE_LABELS, ROLES } from "@/lib/roles"

type RoleSelectProps = {
  value: Role
  onValueChange: (role: Role) => void
}

// Render inside a <FormItem> so the trigger is wired to its <FormLabel>.
export const RoleSelect = ({ value, onValueChange }: RoleSelectProps) => (
  <Select
    value={value}
    onValueChange={(next) => {
      if (isRole(next)) onValueChange(next)
    }}
  >
    <FormControl>
      <SelectTrigger className="w-full">
        <SelectValue />
      </SelectTrigger>
    </FormControl>
    <SelectContent>
      {ROLES.map((role) => (
        <SelectItem key={role} value={role}>
          {ROLE_LABELS[role]}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
)
