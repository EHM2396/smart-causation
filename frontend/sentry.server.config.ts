import * as Sentry from "@sentry/nextjs";

const DSN = process.env.NEXT_PUBLIC_GLITCHTIP_DSN;

if (DSN) {
  Sentry.init({
    dsn: DSN,
    environment: process.env.NODE_ENV,
    tracesSampleRate: 0.1,
  });
}
