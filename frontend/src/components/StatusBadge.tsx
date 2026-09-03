import { CircleSlash, ShieldCheck, Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ROLE_LABELS, type Role, type User } from "@/lib/types";

export function StatusBadge({ user }: { user: Pick<User, "is_active" | "locked_until"> }) {
  const locked =
    user.locked_until && new Date(user.locked_until).getTime() > Date.now();

  if (!user.is_active) {
    return (
      <Badge variant="danger">
        <CircleSlash className="h-3 w-3" />
        Bloklangan
      </Badge>
    );
  }
  if (locked) {
    return (
      <Badge variant="warning">
        <Lock className="h-3 w-3" />
        Vaqtincha qulf
      </Badge>
    );
  }
  return (
    <Badge variant="success">
      <span className="h-1.5 w-1.5 rounded-full bg-success" />
      Faol
    </Badge>
  );
}

export function RoleBadge({ role }: { role: Role }) {
  return (
    <Badge variant={role === "super_admin" ? "accent" : "neutral"}>
      <ShieldCheck className="h-3 w-3" />
      {ROLE_LABELS[role]}
    </Badge>
  );
}
