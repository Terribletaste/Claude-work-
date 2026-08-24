import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Path to 100K — jobs without a degree",
  description:
    "A skill-tree map of US careers that pay over $100,000 a year and do not require a college degree. Answer a few questions to see your viable paths.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <div className="starfield" aria-hidden />
        {children}
      </body>
    </html>
  );
}
