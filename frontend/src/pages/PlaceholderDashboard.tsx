import { motion } from "framer-motion";
import { Construction, type LucideIcon } from "lucide-react";
import { PageTransition } from "@/components/PageTransition";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface Props {
  title: string;
  description: string;
  section: string;
  icon: LucideIcon;
  readOnly?: boolean;
  panels: string[];
}

export function PlaceholderDashboard({
  title,
  description,
  section,
  icon: Icon,
  readOnly,
  panels,
}: Props) {
  return (
    <PageTransition>
      <PageHeader
        title={title}
        description={description}
        actions={
          readOnly ? (
            <Badge variant="warning">Faqat o'qish (read-only)</Badge>
          ) : (
            <Badge variant="accent">{section}</Badge>
          )
        }
      />

      <div className="grid grid-cols-3 gap-4">
        {panels.map((p, i) => (
          <motion.div
            key={p}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05, duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          >
            <Card className="h-40">
              <CardContent className="flex h-full flex-col justify-between">
                <div className="flex items-center gap-2 text-content-muted">
                  <Icon className="h-4 w-4 text-accent" />
                  <span className="text-sm font-medium">{p}</span>
                </div>
                <div className="space-y-2">
                  <div className="h-2 w-3/4 rounded-full bg-surface-overlay" />
                  <div className="h-2 w-1/2 rounded-full bg-surface-overlay" />
                </div>
                <p className="text-2xs text-content-faint">
                  Keyingi bosqichda to'ldiriladi
                </p>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <Card className="mt-4">
        <CardContent className="flex items-center gap-3 text-sm text-content-muted">
          <Construction className="h-4 w-4 text-warning" />
          Bu sahifa hozircha placeholder. Auth &amp; RBAC bosqichi yakunlangan —
          jadval va grafiklar keyingi bosqichda qo'shiladi.
        </CardContent>
      </Card>
    </PageTransition>
  );
}
