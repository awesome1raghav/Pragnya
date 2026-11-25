import type { Metadata, Viewport } from "next";
import { Host_Grotesk, JetBrains_Mono, Source_Serif_4 } from "next/font/google";
import "@/styles/globals.css";

const display = Host_Grotesk({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-host", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-jb", display: "swap" });
const serif = Source_Serif_4({ subsets: ["latin"], weight: ["400", "600"], style: ["normal", "italic"], variable: "--font-serif", display: "swap" });

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:8080'),
  title: "NEXTRON — Digital media verification workspace",
  description: "Evidence-led media verification for forensic investigators.",
};

export const viewport: Viewport = { themeColor: "#0b0a09" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  // marks that script runs, before the first paint, so the landing entrance can start hidden without a flash
  const js = "document.documentElement.classList.add('js')";
  return <html lang="en" className={`${display.variable} ${mono.variable} ${serif.variable}`} data-type="software" suppressHydrationWarning>
    <head><script dangerouslySetInnerHTML={{ __html: js }} /></head>
    <body>{children}</body>
  </html>;
}
