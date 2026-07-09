/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // `standalone` output keeps the production Docker image small (Phase 8).
  output: "standalone",
};

module.exports = nextConfig;
