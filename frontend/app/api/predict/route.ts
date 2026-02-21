/**
 * Next.js API Route：/api/predict
 *
 * 【為什麼需要這個 proxy？】
 *
 * 瀏覽器的 CORS 機制：
 *   前端（vercel.app）→ 直接打 Render API → 瀏覽器先送 OPTIONS preflight
 *   → 若 Render 的 CORS header 不完整 → "Failed to fetch"
 *
 * 使用 Next.js API Route 作為 proxy：
 *   前端（vercel.app）→ 打 /api/predict（同源，無 CORS 問題）
 *   → Next.js server → 打 Render API（server-to-server，無 CORS 限制）
 *
 * 優點：
 *   ✅ 完全繞過瀏覽器 CORS 限制
 *   ✅ 隱藏後端 API 網址
 *   ✅ 可加入 rate limiting、logging、auth
 */

import { NextRequest, NextResponse } from "next/server";

// Render 後端 URL（從環境變數讀取）
const BACKEND_URL = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Server-side 呼叫 Render API（不受 CORS 限制）
    const response = await fetch(`${BACKEND_URL}/predict`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // 若後端有 API key 驗證，可在此加入
        // "X-API-Key": process.env.API_SECRET_KEY ?? "",
      },
      body: JSON.stringify(body),
      // 設定 timeout（Render 免費方案 cold start 可能需要 30 秒）
      signal: AbortSignal.timeout(60_000),
    });

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(data, { status: response.status });
    }

    return NextResponse.json(data);

  } catch (error: unknown) {
    const isTimeout = error instanceof Error && error.name === "TimeoutError";

    console.error("[/api/predict proxy error]", error);

    return NextResponse.json(
      {
        error: isTimeout
          ? "後端服務啟動中，請稍後再試（免費方案首次請求需等待 30-60 秒）"
          : "後端服務連線失敗，請確認 Render 服務狀態",
        detail: error instanceof Error ? error.message : "Unknown error",
      },
      { status: isTimeout ? 503 : 502 }
    );
  }
}

// 支援 OPTIONS preflight（雖然同源不需要，但防止意外）
export async function OPTIONS() {
  return new NextResponse(null, { status: 200 });
}
