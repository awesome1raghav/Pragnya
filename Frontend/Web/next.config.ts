import type { NextConfig } from 'next';

// Security headers (Step 9). The Content-Security-Policy is only sent by production builds: the dev server needs
// eval for hot reloading. The API origin comes from the same variable the client uses.
const api = new URL(process.env.NEXT_PUBLIC_NEXTRON_API ?? 'http://localhost:8000/api/v1');
const apiOrigin = api.origin;
const wsOrigin = apiOrigin.replace(/^http/, 'ws');
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",            // Next.js inline bootstrap scripts
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: blob: ${apiOrigin}`,       // evidence previews, heatmaps, artifacts
  `media-src 'self' blob: ${apiOrigin}`,           // video and audio playback
  `connect-src 'self' ${apiOrigin} ${wsOrigin}`,   // REST and live events
  "font-src 'self' data:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join('; ');

const always = [
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'Referrer-Policy', value: 'no-referrer' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(), payment=()' },
];

const config: NextConfig = {
  poweredByHeader: false,
  // the Docker image runs the self-contained server (Infrastructure/Docker/Frontend.Dockerfile); `next start` stays as it is locally
  ...(process.env.NEXT_OUTPUT === 'standalone' ? { output: 'standalone' as const } : {}),
  async headers() {
    const headers = process.env.NODE_ENV === 'production' ? [...always, { key: 'Content-Security-Policy', value: csp }] : always;
    return [{ source: '/:path*', headers }];
  },
  async redirects() {
    return [
      // `/` is the landing page again (operator request, 26 Nov 2026; reverses default D-1). It is also at /about.
      // the old single-page workspace address keeps working for bookmarks
      { source: '/workspace', destination: '/dashboard', permanent: false },
    ];
  },
};

export default config;
