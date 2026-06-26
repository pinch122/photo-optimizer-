import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "PhotoMind AI",
  description: "AI-Powered Personal Memory Assistant",
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
