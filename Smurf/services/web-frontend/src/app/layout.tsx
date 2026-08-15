import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Smurf Platform | Real-Time IoT Control Room",
  description: "Enterprise Stream Processing & Multi-Agent AI Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
