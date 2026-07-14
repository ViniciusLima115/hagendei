import type { NextConfig } from "next";

const apiOrigin = (() => {
  try {
    return new URL(process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").origin;
  } catch {
    return "http://127.0.0.1:8000";
  }
})();

const isDevelopment = process.env.NODE_ENV !== "production";
const scriptSource = `script-src 'self' 'unsafe-inline'${isDevelopment ? " 'unsafe-eval'" : ""}`;
const connectSource = isDevelopment
  ? `connect-src 'self' ${apiOrigin} http://localhost:8000 http://127.0.0.1:8000 ws://localhost:* ws://127.0.0.1:*`
  : `connect-src 'self' ${apiOrigin}`;

const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "frame-ancestors 'none'",
  "object-src 'none'",
  "form-action 'self'",
  scriptSource,
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self' data:",
  "img-src 'self' data: blob: https:",
  connectSource,
].join("; ");

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
        ],
      },
    ];
  },
};

export default nextConfig;
