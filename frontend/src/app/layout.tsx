import type { Metadata } from "next";
import "./globals.css";
import Providers from "@/components/Providers";
import Sidebar from "@/components/layout/Sidebar";
import MobileNav from "@/components/layout/MobileNav";

export const metadata: Metadata = {
  title: "PhotoMind AI — Personal Memory Assistant",
  description:
    "AI-powered personal memory assistant. Search, organize, and understand your photo gallery using natural language.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased">
        <Providers>
          <div className="flex min-h-screen">
            {/* Desktop sidebar */}
            <Sidebar />

            {/* Main content */}
            <main className="flex-1 min-w-0">
              <div className="px-4 sm:px-6 lg:px-8 py-6 pb-20 lg:pb-6 max-w-7xl mx-auto">
                {children}
              </div>
            </main>
          </div>

          {/* Mobile bottom nav */}
          <MobileNav />
        </Providers>
      </body>
    </html>
  );
}


