import * as DialogPrimitive from "@radix-ui/react-dialog";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Boshqariladigan (controlled) modal. Foydalanish:
 *
 *   <Dialog open={open} onOpenChange={setOpen}>
 *     <DialogContent open={open} title="...">...</DialogContent>
 *   </Dialog>
 */
export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

const MotionOverlay = motion(DialogPrimitive.Overlay);
const MotionContent = motion(DialogPrimitive.Content);

interface DialogContentProps {
  open: boolean;
  children: ReactNode;
  className?: string;
  title: string;
  description?: string;
}

export function DialogContent({
  open,
  children,
  className,
  title,
  description,
}: DialogContentProps) {
  return (
    <AnimatePresence>
      {open && (
        <DialogPrimitive.Portal forceMount>
          <MotionOverlay
            forceMount
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
          />
          <div className="fixed inset-0 z-50 grid place-items-center p-4">
            <MotionContent
              forceMount
              className={cn(
                "relative w-full max-w-lg rounded-lg border border-line-strong bg-surface-raised shadow-overlay",
                className,
              )}
              initial={{ opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="flex items-start justify-between gap-4 p-5 border-b border-line">
                <div className="space-y-1">
                  <DialogPrimitive.Title className="text-sm font-semibold text-content">
                    {title}
                  </DialogPrimitive.Title>
                  {description && (
                    <DialogPrimitive.Description className="text-xs text-content-muted">
                      {description}
                    </DialogPrimitive.Description>
                  )}
                </div>
                <DialogPrimitive.Close className="rounded-md p-1 text-content-faint transition-colors hover:bg-surface-overlay hover:text-content">
                  <X className="h-4 w-4" />
                </DialogPrimitive.Close>
              </div>
              <div className="p-5">{children}</div>
            </MotionContent>
          </div>
        </DialogPrimitive.Portal>
      )}
    </AnimatePresence>
  );
}

export function DialogFooter({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("mt-6 flex items-center justify-end gap-2", className)}
      {...props}
    />
  );
}
