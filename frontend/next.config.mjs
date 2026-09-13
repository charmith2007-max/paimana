/** @type {import('next').NextConfig} */
const API = (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/paimana-api/:path*',
        destination: `${API}/:path*`,
      },
    ]
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
