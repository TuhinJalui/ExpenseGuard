/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    // Backend API URL — override via NEXT_PUBLIC_API_URL environment variable
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
};

module.exports = nextConfig;
