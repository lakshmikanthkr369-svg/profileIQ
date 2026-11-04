const api = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
const supa = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const rzp = "https://*.razorpay.com";
// Only the hosts the app really talks to. 'unsafe-inline' is needed for Next's own bootstrap scripts.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline' ${rzp}`,
  "style-src 'self' 'unsafe-inline'",
  `connect-src 'self' ${api} ${supa} ${rzp}`,
  `frame-src ${rzp}`,
  `img-src 'self' data: https: blob:`,
  `font-src 'self' data:`,
  "object-src 'none'",
  "base-uri 'self'",
  `form-action 'self' ${rzp}`,
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  async headers() {
    return [
      { source: "/:path*", headers: securityHeaders },
      // Pages are prebuilt (instant, and prefetched on hover/scroll) but the browser re-checks them on every visit,
      // so a phone never keeps a page that points at files from an older deploy. Hashed assets stay cached.
      { source: "/((?!_next/static|_next/image|.*\\..*).*)", headers: [{ key: "Cache-Control", value: "no-cache, must-revalidate" }] },
    ];
  },
};
export default nextConfig;
