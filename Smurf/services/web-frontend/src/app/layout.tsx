import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SMURF | Smart Agriculture Control Room",
  description: "Multi-Agent AI Smart Farm Operations & Resource Coordination — SEAL Hackathon Summer 2026",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
        <meta name="theme-color" content="#071108" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
