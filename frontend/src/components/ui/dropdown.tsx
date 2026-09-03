import * as DM from "@radix-ui/react-dropdown-menu";
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

export const Dropdown = DM.Root;
export const DropdownTrigger = DM.Trigger;

export const DropdownContent = forwardRef<
  React.ElementRef<typeof DM.Content>,
  React.ComponentPropsWithoutRef<typeof DM.Content>
>(({ className, align = "start", sideOffset = 4, ...props }, ref) => (
  <DM.Portal>
    <DM.Content
      ref={ref}
      align={align}
      sideOffset={sideOffset}
      className={cn(
        "z-50 min-w-[10rem] overflow-hidden rounded-md border border-line-strong bg-surface-overlay p-1 shadow-overlay",
        "data-[state=open]:animate-fade-in",
        className,
      )}
      {...props}
    />
  </DM.Portal>
));
DropdownContent.displayName = "DropdownContent";

export const DropdownItem = forwardRef<
  React.ElementRef<typeof DM.Item>,
  React.ComponentPropsWithoutRef<typeof DM.Item> & { destructive?: boolean }
>(({ className, destructive, ...props }, ref) => (
  <DM.Item
    ref={ref}
    className={cn(
      "flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-xs font-medium outline-none transition-colors",
      "data-[highlighted]:bg-surface-raised data-[disabled]:pointer-events-none data-[disabled]:opacity-40",
      destructive
        ? "text-danger data-[highlighted]:bg-danger/10"
        : "text-content-muted data-[highlighted]:text-content",
      className,
    )}
    {...props}
  />
));
DropdownItem.displayName = "DropdownItem";

export const DropdownSeparator = () => (
  <DM.Separator className="my-1 h-px bg-line" />
);
