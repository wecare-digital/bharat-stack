import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

// Resolve this file's directory reliably. `import.meta.dirname` can be
// undefined depending on how Next evaluates the config, whereas
// `import.meta.url` is always present in an ES module.
const projectRoot = dirname( fileURLToPath( import.meta.url ) );

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  trailingSlash: true,
  output: process.env.NODE_ENV === 'production' ? 'export' : undefined,
  // Pin the workspace root to this folder so Turbopack doesn't walk up to the
  // parent dir's stray package-lock.json / node_modules (the repo is nested
  // inside another npm project on some dev machines). On CI the repo is
  // checked out standalone, so this is a no-op there.
  turbopack: {
    root: projectRoot,
  },
  outputFileTracingRoot: projectRoot,
  images: {
    unoptimized: true
  },
  // Security headers — applied during static export build
  headers: async () => [
    {
      source: '/(.*)',
      headers: [
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'X-Frame-Options', value: 'DENY' },
        { key: 'X-XSS-Protection', value: '1; mode=block' },
        { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        { key: 'Permissions-Policy', value: 'camera=(), microphone=(self), geolocation=()' },
      ],
    },
  ],
  env: {
    NEXT_PUBLIC_SEND_MODE: 'LIVE',
    NEXT_PUBLIC_ENV: 'production',
    NEXT_PUBLIC_GA_MEASUREMENT_ID: 'G-S3G6REP6Q7',
  }
}

export default nextConfig
