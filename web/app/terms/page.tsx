import type { Metadata } from "next";
import LegalPage from "@/components/LegalPage";

export const metadata: Metadata = { title: "Terms of Service — ProfileIQ" };
export default function Page() { return <LegalPage file="terms" kind="doc" />; }
