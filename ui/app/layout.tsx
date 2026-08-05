import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  title: "LoanRiskCalculator | Loan risk decision intelligence",
  description:
    "A versioned, model-assisted workspace for pre-pricing loan risk assessment.",
  openGraph: {
    title: "LoanRiskCalculator",
    description: "Decision intelligence for responsible lending",
    images: [{ url: "/og.png", width: 1536, height: 909, alt: "LoanRiskCalculator decision intelligence" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "LoanRiskCalculator",
    description: "Decision intelligence for responsible lending",
    images: ["/og.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
