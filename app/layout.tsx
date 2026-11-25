import type { Metadata, Viewport } from "next";
import { Host_Grotesk, JetBrains_Mono, Source_Serif_4 } from "next/font/google";
import "./globals.css";
import Loader from "./loader";

const display = Host_Grotesk({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-host", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-jb", display: "swap" });
const serif = Source_Serif_4({ subsets: ["latin"], weight: ["400", "600"], style: ["normal", "italic"], variable: "--font-serif", display: "swap" });

export const metadata: Metadata = {
  title: "NEXTRON — Digital media verification workspace",
  description: "Evidence-led media verification for forensic investigators.",
};

export const viewport: Viewport = { themeColor: "#0b0a09" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  // returning visitors in the same session skip the loader before the first paint
  const seen = "try{if(sessionStorage.getItem('nx-intro')){var d=document.documentElement;d.classList.add('nx-seen');d.dataset.nxReady='1'}}catch(e){}";
  return <html lang="en" className={`${display.variable} ${mono.variable} ${serif.variable}`} data-type="software" suppressHydrationWarning>
    <head><script dangerouslySetInnerHTML={{ __html: seen }} /></head>
    <body><Loader />{children}</body>
  </html>;
}
