import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Dev HMR treats 127.0.0.1 and localhost as different origins in Next 16
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
