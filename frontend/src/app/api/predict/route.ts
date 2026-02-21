/**
 * Next.js App Router API Route
 * 路徑：src/app/api/predict/route.ts
 * URL： /api/predict
 *
 * 這個 Proxy 解決 CORS 問題：
 *   瀏覽器 → /api/predict（同源，無 CORS）
 *   Next.js Server → Render（Server-to-Server，無 CORS）
 */

import { NextRequest, NextResponse } from "next/server";

// Render 後端網址（從 Vercel 環境變數讀取）
const BACKEND_URL =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const upstream = await fetch(`${BACKEND_URL}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      // Render 免費方案 cold start 最多需要 60 秒
      signal: AbortSignal.timeout(65_000),
    });

    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });

  } catch (err: unknown) {
    const isTimeout =
      err instanceof Error &&
      (err.name === "TimeoutError" || err.name === "AbortError");

    return NextResponse.json(
      {
        error: isTimeout
          ? "後端啟動中，請稍後重試（免費方案首次請求需 30-60 秒）"
          : "後端連線失敗",
        detail: err instanceof Error ? err.message : String(err),
      },
      { status: isTimeout ? 503 : 502 }
    );
  }
}

export async function GET() {
  // 健康檢查：可直接在瀏覽器打 /api/predict 確認 route 存在
  return NextResponse.json({
    status: "ok",
    backend: BACKEND_URL,
    usage: "POST /api/predict with JSON body",
  });
}
