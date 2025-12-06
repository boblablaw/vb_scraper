import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import SettingsDrawer from "@/components/SettingsDrawer";
import "./globals.css";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "VB Scraper Portal",
  description:
    "Browse NCAA Division 1 volleyball teams and rosters powered by the vb_scraper API.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} app-body`}>
        <div className="shell">
          <header className="site-header">
            <div className="shell-inner header-content">
              <Link href="/" className="logo">
                VB Portal
              </Link>
              <div className="nav-group">
                <nav className="nav">
                  <Link href="/">Home</Link>
                  <Link href="/teams">Teams</Link>
                  <Link href="/players">Players</Link>
                </nav>
                <SettingsDrawer />
              </div>
            </div>
          </header>
          <main className="shell-inner content">{children}</main>
          <footer className="site-footer">
            <div className="shell-inner footer-text">
              Data refreshed via vb_scraper &middot; API URL:{" "}
              {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
