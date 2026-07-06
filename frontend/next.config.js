/** @type {import('next').NextConfig} */
const nextConfig = {
  // Required for Docker standalone deployment (frontend/Dockerfile)
  output: "standalone",
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
};

module.exports = nextConfig;
