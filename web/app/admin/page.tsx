import type { Metadata } from "next";
import AdminApp from "@/components/AdminApp";

export const metadata: Metadata = { title: "Admin — ProfileIQ", robots: { index: false, follow: false } };
export default function Page() { return <AdminApp />; }
