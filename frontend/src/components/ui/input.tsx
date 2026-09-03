import { forwardRef } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "flex h-10 w-full rounded-md border border-line-strong bg-surface-raised px-3 py-2 text-sm text-content",
      "placeholder:text-content-faint",
      "transition-all duration-150 ease-out-expo",
      "focus-visible:outline-none focus-visible:border-accent focus-visible:ring-4 focus-visible:ring-accent/15",
      "disabled:cursor-not-allowed disabled:opacity-50",
      "aria-[invalid=true]:border-danger aria-[invalid=true]:ring-danger/15",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";

export const Label = forwardRef<
  HTMLLabelElement,
  React.LabelHTMLAttributes<HTMLLabelElement>
>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn(
      "text-xs font-medium text-content-muted mb-1.5 block tracking-wide",
      className,
    )}
    {...props}
  />
));
Label.displayName = "Label";
