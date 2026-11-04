import type { Metadata } from "next";
import LegalPage from "@/components/LegalPage";

export const metadata: Metadata = { title: "About Us — ProfileIQ" };
export default function Page() { return <LegalPage file="about" kind="about" />; }
