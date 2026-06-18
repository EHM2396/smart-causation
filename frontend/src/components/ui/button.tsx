import * as React from "react";
import { cn } from "@/lib/utils";
import { cva, type VariantProps } from "class-variance-authority";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-emerald-600 hover:bg-emerald-700 text-white shadow-lg",
        destructive: "bg-red-600 text-white hover:bg-red-700",
        outline: "border hover:text-[var(--text-primary)]",
        ghost: "hover:bg-[var(--bg-elevated)]",
        secondary: "border",
        success: "bg-emerald-600 text-white hover:bg-emerald-700 shadow-lg shadow-emerald-500/20",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 px-3 text-xs",
        lg: "h-11 px-6",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, style, ...props }, ref) => {
    const themedStyle =
      variant === "default"
        ? {
            boxShadow: "0 4px 14px rgb(5 150 105 / 0.35)",
            ...style,
          }
        : variant === "outline"
          ? {
              borderColor: "var(--border-soft)",
              color: "var(--text-secondary)",
              backgroundColor: "var(--bg-surface)",
              ...style,
            }
          : variant === "secondary"
            ? {
                borderColor: "var(--border-soft)",
                color: "var(--text-secondary)",
                backgroundColor: "var(--bg-elevated)",
                ...style,
              }
            : variant === "ghost"
              ? {
                  color: "var(--text-secondary)",
                  ...style,
                }
              : style;

    return (
      <button
        ref={ref}
        className={cn(buttonVariants({ variant, size, className }))}
        style={{
          ...(themedStyle || {}),
          outlineColor: "var(--ring)",
        }}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
