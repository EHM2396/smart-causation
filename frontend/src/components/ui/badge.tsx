import { cn } from "@/lib/utils";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "success" | "warning" | "info" | "purple";
  className?: string;
}

// Uses CSS status tokens so colors adapt to light & dark mode automatically
const variantStyle: Record<NonNullable<BadgeProps["variant"]>, React.CSSProperties> = {
  default: {
    borderColor: "var(--border-soft)",
    color: "var(--text-secondary)",
    backgroundColor: "color-mix(in srgb, var(--text-muted) 16%, transparent)",
  },
  success: {
    borderColor: "var(--success-border)",
    color: "var(--success-text)",
    backgroundColor: "var(--success-bg)",
  },
  warning: {
    borderColor: "var(--warning-border)",
    color: "var(--warning-text)",
    backgroundColor: "var(--warning-bg)",
  },
  info: {
    borderColor: "var(--info-border)",
    color: "var(--info-text)",
    backgroundColor: "var(--info-bg)",
  },
  purple: {
    borderColor: "var(--purple-border)",
    color: "var(--purple-text)",
    backgroundColor: "var(--purple-bg)",
  },
};

export function Badge({ children, variant = "default", className }: BadgeProps) {
  return (
    <span
      className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium", className)}
      style={variantStyle[variant]}
    >
      {children}
    </span>
  );
}
