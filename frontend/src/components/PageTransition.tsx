import type { ReactNode } from "react";

/**
 * Sahifa o'tish animatsiyasi endi `AppShell` da markazlashgan (`useOutlet` +
 * `AnimatePresence`). Bu komponent orqaga moslik uchun qoldirilgan — oddiy o'ram.
 */
export function PageTransition({ children }: { children: ReactNode }) {
  return <div className="h-full">{children}</div>;
}
