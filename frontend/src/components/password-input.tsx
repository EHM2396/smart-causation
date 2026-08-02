"use client";

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

interface PasswordInputProps {
  id?: string;
  name?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  autoComplete?: string;
  required?: boolean;
  minLength?: number;
}

export function PasswordInput({
  id,
  name,
  value,
  onChange,
  placeholder = "••••••••",
  autoComplete = "current-password",
  required,
  minLength,
}: PasswordInputProps) {
  const [show, setShow] = useState(false);

  return (
    <div className="relative">
      <input
        id={id}
        name={name}
        type={show ? "text" : "password"}
        required={required}
        minLength={minLength}
        autoComplete={autoComplete}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="w-full rounded-lg border px-3 py-2 pr-10 text-sm outline-none transition-colors"
        style={{
          backgroundColor: "var(--bg-elevated)",
          borderColor: "var(--border-soft)",
          color: "var(--text-primary)",
        }}
      />
      <button
        type="button"
        onClick={() => setShow((v) => !v)}
        tabIndex={-1}
        aria-label={show ? "Ocultar contraseña" : "Ver contraseña"}
        className="absolute inset-y-0 right-0 flex items-center px-3 transition-colors"
        style={{ color: "var(--text-muted)" }}
      >
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}
