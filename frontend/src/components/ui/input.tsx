import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50 transition-colors",
        className
      )}
      style={{
        borderColor: "var(--border-soft)",
        backgroundColor: "var(--bg-surface)",
        color: "var(--text-primary)",
        outlineColor: "var(--ring)",
      }}
      {...props}
    />
  )
);
Input.displayName = "Input";

export { Input };
