import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "永豐銀行 | AI法金貸款利率試算",
  description: "中小企業信貸風險評估與貸款利率智慧試算平台 — 永豐銀行 SinoPac Bank",
  keywords: "永豐銀行, 中小企業, 貸款, 利率試算, 信用風險",
  authors: [{ name: "永豐銀行 SinoPac Bank" }],
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: "#C8102E",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-TW">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* Dynamic favicon: red square with S */}
        <link
          rel="icon"
          href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%23C8102E'/><text x='50%25' y='55%25' font-family='serif' font-size='22' font-weight='bold' fill='white' text-anchor='middle' dominant-baseline='middle'>S</text></svg>"
        />
      </head>
      <body
        style={{
          margin: 0,
          padding: 0,
          background: "#E0E0E0",
          fontFamily:
            "'Noto Sans TC', 'Microsoft JhengHei', 'PingFang TC', 'Heiti TC', sans-serif",
          WebkitFontSmoothing: "antialiased",
          MozOsxFontSmoothing: "grayscale",
          overscrollBehavior: "none",
        }}
      >
        {children}
      </body>
    </html>
  );
}
