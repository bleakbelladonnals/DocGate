import type { Metadata } from "next";
import "./globals.css";
export const metadata:Metadata={title:"DocGate",description:"Evidence-first Markdown acceptance"};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="zh-CN"><body>{children}</body></html>}
