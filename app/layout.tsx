import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./workbench.css";
import "./about.css";
import "./decision-validation.css";
import "./queue-tools.css";
import "./mission-control.css";
const sans = Geist({ variable: "--font-sans", subsets: ["latin"] });
const mono = Geist_Mono({ variable: "--font-mono", subsets: ["latin"] });
export const metadata: Metadata = {
  title: "Procurement Modernization | Migration Control Workbench",
  description:
    "A procurement data migration validation, exception review and release-readiness prototype.",
  other: { "codex-preview": "development" },
  icons: { icon: "/favicon.svg" },
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${sans.variable} ${mono.variable}`}>{children}</body>
    </html>
  );
}
