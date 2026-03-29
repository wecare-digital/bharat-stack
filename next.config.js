/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  trailingSlash: true,
  output: 'standalone',
  images: {
    unoptimized: true
  },
  env: {
    NEXT_PUBLIC_SEND_MODE: 'LIVE',
    NEXT_PUBLIC_ENV: 'production'
  }
}

export default nextConfig
