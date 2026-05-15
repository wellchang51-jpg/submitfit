import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "學習歷程 PDF 壓縮到 4MB 以下",
  description:
    "專為高中生學習歷程設計的 PDF 壓縮工具。上傳 PDF 後，系統會自動壓縮到 4MB 以下，方便上傳學習歷程檔案。",
  openGraph: {
    title: "學習歷程 PDF 壓縮到 4MB 以下",
    description:
      "一鍵壓縮 PDF 到 4MB 以下，專為高中生學習歷程檔案上傳設計。",
    url: "https://submitfit.vercel.app",
    siteName: "Drago's project",
    type: "website",
    locale: "zh_TW",
  },
  twitter: {
    card: "summary",
    title: "學習歷程 PDF 壓縮到 4MB 以下",
    description:
      "一鍵壓縮 PDF 到 4MB 以下，專為高中生學習歷程檔案上傳設計。",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}