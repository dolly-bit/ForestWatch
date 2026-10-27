import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ForestWatch",
  description: "Candidate vegetation-loss areas from Sentinel-2 change detection",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
