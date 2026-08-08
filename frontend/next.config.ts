import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  compiler: {
    removeConsole: {
      exclude: ["error", "warn"],
    },
  },
};

export default withSentryConfig(nextConfig, {
  silent: true,
  disableLogger: true,
  // GlitchTip no necesita source maps subidos; los desactivamos para no exponer código fuente.
  sourcemaps: { disable: true },
  // No se requiere auth token de Sentry.io ya que usamos GlitchTip.
  authToken: undefined,
});
