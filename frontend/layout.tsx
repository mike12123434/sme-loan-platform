import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "永豐銀行 | AI法金貸款利率試算",
  description: "中小企業信貸風險評估與貸款利率智慧試算平台",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-TW">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
        <meta name="theme-color" content="#C8102E" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body style={{ margin: 0, padding: 0, background: "#E0E0E0" }}>
        {children}
      </body>
    </html>
  );
}
