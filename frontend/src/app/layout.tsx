import type { Metadata } from "next";
import "highlight.js/styles/github-dark.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Voice AI Assistant",
  description: "Self-hosted Voice + Text AI Assistant",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
