/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'export',
  trailingSlash: true,
  images: {
    unoptimized: true
  },
  env: {
    NEXT_PUBLIC_SEND_MODE: 'LIVE',
    NEXT_PUBLIC_ENV: 'production'
  }
}

export default nextConfig
