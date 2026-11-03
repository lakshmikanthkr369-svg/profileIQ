import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ProfileIQ — AI Resume Intelligence",
  description: "Score your resume against any job description and see exactly which keywords you're missing.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0e0e0e" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (<html lang="en"><body>{children}</body></html>);
}
