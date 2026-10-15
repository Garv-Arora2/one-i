import type { NextConfig } from "next";

const API_BASE_URL =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
        pathname: "/photo-*",
      },
    ],
  },
  // Browser calls go through the site's own origin, so the session cookie is
  // first-party here and in production (Vercel and the API live on different
  // domains, and browsers drop cross-site cookies).
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_BASE_URL}/:path*` }];
  },
};

export default nextConfig;
