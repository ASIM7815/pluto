import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "P L U T O — Linux Desktop AI Assistant",
  description: "Futuristic AI operating layer for Linux computer control using voice and natural language.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased bg-[#050506] text-[#f5f5f5]">
        {children}
      </body>
    </html>
  );
}
