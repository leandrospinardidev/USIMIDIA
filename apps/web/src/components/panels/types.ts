import type { UserRole } from "../../types";

export interface StandardPanelProps {
  role: UserRole;
  statusFilters: readonly string[];
  isActive: boolean;
  onError: (message: string | null) => void;
  onSuccess: (message: string | null) => void;
}
