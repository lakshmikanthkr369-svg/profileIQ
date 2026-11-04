import type { Metadata } from "next";
import AccountPage from "@/components/AccountPage";

export const metadata: Metadata = { title: "Manage plan — ProfileIQ" };
export default function Page() { return <AccountPage kind="account" />; }
