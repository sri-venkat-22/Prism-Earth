/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emit a self-contained server bundle (.next/standalone) for a small, secure
  // production image (SRS §32, §33). Enabled only for the Docker build so local
  // `next start` (dev, E2E) keeps working without the standalone caveat.
  output: process.env.NEXT_OUTPUT_STANDALONE === "1" ? "standalone" : undefined,
};

export default nextConfig;
