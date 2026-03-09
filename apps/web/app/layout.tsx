import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Notion Graph",
  description: "Notion-rooted knowledge graph explorer"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
