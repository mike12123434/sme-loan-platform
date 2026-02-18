# 永豐金控 AI法金貸款利率試算平台
## 完整專案建置指南（零基礎到上線）

---

## 目錄
1. [整體架構說明](#整體架構)
2. [Step 1：後端 FastAPI](#step-1-fastapi-backend)
3. [Step 2：訓練 ML 模型](#step-2-訓練-ml-模型)
4. [Step 3：利率定價邏輯說明](#step-3-利率定價邏輯)
5. [Step 4：前端 Next.js](#step-4-nextjs-frontend)
6. [Step 5：解決 CORS 串接問題](#step-5-cors-串接)
7. [Step 6：部署到 Render + Vercel](#step-6-部署)
8. [Step 7：Demo 展示流程](#step-7-demo展示)
9. [常見錯誤排除](#常見錯誤排除)

---

## 整體架構

```
瀏覽器（使用者）
    │
    ▼
Next.js Frontend（Vercel）
    │  POST /predict（JSON）
    ▼
FastAPI Backend（Render/Railway）
    │  載入 model.pkl
    ▼
ML 模型（Stacking）＋ 台灣市場利率層
    │
    ▼
JSON Response（利率、風險等級、成分明細）
```

### 資料夾結構（完整）

```
sme-loan-platform/
├── backend/                     ← FastAPI 後端
│   ├── main.py                  ← 主程式（API路由、定價邏輯）
│   ├── train_model.py           ← 模型訓練腳本
│   ├── model.pkl                ← 訓練好的模型（執行 train_model.py 產生）
│   ├── nigeria_sme_loans_full_sample.csv  ← 訓練資料集
│   ├── requirements.txt         ← Python 套件清單
│   ├── .env.example             ← 環境變數範本
│   ├── .env                     ← 實際環境變數（不上傳 Git）
│   └── Procfile                 ← Render 部署設定
│
├── frontend/                    ← Next.js 前端（需手動初始化）
│   ├── src/
│   │   └── app/
│   │       ├── page.tsx         ← 主頁面（已提供完整程式碼）
│   │       ├── layout.tsx       ← 根版型
│   │       └── globals.css      ← 全域樣式
│   ├── .env.local               ← 前端環境變數
│   ├── next.config.js           ← Next.js 設定
│   ├── tailwind.config.js       ← Tailwind 設定
│   └── package.json
│
└── README.md
```

---

## Step 1：FastAPI Backend

### 為什麼用 FastAPI？
- 比 Flask 快 3-5 倍，支援 async
- 自動產生 Swagger UI（`/docs`），方便測試
- Pydantic 自動做輸入驗證，防止 422 錯誤
- Production-ready，Render/Railway 都支援

### 1.1 建立 Python 虛擬環境

```bash
# 進入後端資料夾
cd backend/

# 建立虛擬環境（Python 3.10+）
python3 -m venv venv

# 啟動虛擬環境
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 安裝套件
pip install -r requirements.txt
```

### 1.2 複製環境變數

```bash
cp .env.example .env
# 用文字編輯器打開 .env，根據需要修改
```

### 1.3 啟動後端（開發模式）

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

成功後終端機顯示：
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     ✅ 模型載入成功（或 ⚠️ 找不到 model.pkl）
```

### 1.4 測試 API（用瀏覽器）

打開 http://localhost:8000/docs 即可看到 Swagger UI，直接在網頁測試。

### 1.5 用 Postman 測試

**POST** `http://localhost:8000/predict`

Headers：
```
Content-Type: application/json
```

Body（raw JSON）：
```json
{
  "annual_revenue_ntd": 5000000,
  "years_in_business": 5,
  "num_employees": 20,
  "business_sector": "manufacturing",
  "credit_score": 680,
  "loan_amount_ntd": 2000000,
  "tenor_months": 36,
  "collateral_value_ntd": 2500000,
  "is_existing_customer": false,
  "has_credit_guarantee": false
}
```

預期回應（200 OK）：
```json
{
  "final_rate": 0.0523,
  "final_rate_pct": "5.23%",
  "pd_score": 0.0312,
  "risk_grade": 3,
  "risk_grade_name": "尚可",
  ...
}
```

---

## Step 2：訓練 ML 模型

### 為什麼需要先訓練模型？
FastAPI 啟動時載入 `model.pkl`。沒有這個檔案，系統仍可運行（用規則式定價替代），但不會有 ML 調整值。

### 2.1 將資料集放到 backend/ 資料夾

```bash
# 確認資料集在正確位置
ls backend/nigeria_sme_loans_full_sample.csv
```

### 2.2 執行訓練

```bash
cd backend/
python train_model.py
```

訓練過程（約 2-5 分鐘）：
```
📥 讀取資料：nigeria_sme_loans_full_sample.csv
   資料筆數：1000
🔢 特徵數量：13
   違約率：16.3%
🤖 訓練 Stacking 集成模型...
   ✅ ROC AUC：0.8234
💾 model.pkl 已儲存！
```

### 2.3 重啟 FastAPI

```bash
# Ctrl+C 停止，然後重新啟動
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

看到 `✅ 模型載入成功` 代表 ML 模型啟用。

---

## Step 3：利率定價邏輯

### 最終利率公式

```
最終利率 = 市場基準 + 信用風險溢酬 + 負債比加成
         + 預期損失成本 + 資金成本 + 目標利差
         + 期限溢酬 + 規模折扣 + 產業溢酬
         + 市場競爭調整 + 客戶關係折扣 + 信保折扣
         + ML模型微調
```

### 各成分說明

| 成分 | 數值範圍 | 設計依據 |
|------|---------|---------|
| 市場基準利率 | 2.00% | 台灣央行重貼現率 1.875%＋銀行溢酬 |
| 信用評分溢酬 | 0-8% | 750分以上0%，300分以下+8% |
| 負債比加成 | 0-5% | DBR≤50%不加，超過300%加3% |
| 預期損失成本 | PD×LGD | LGD=40%，擔保品可減少最多40% |
| 資金成本 | 1.0% | 銀行存款成本＋管理成本 |
| 目標利差 | 1.5% | 銀行獲利目標 |
| 期限溢酬 | 0.15%×年數 | 長期不確定性補償 |
| 規模折扣 | 最多-1% | 大額貸款規模經濟 |
| 產業溢酬 | 0-0.45% | 製造/科技0%，農業最高 |
| 競爭調整 | -0.5% | 台灣銀行業競爭激烈 |
| 客戶折扣 | -0.3% | 既有客戶優惠 |
| 信保折扣 | -0.25% | 信保基金擔保降低銀行風險 |
| ML微調 | ±0.5% | 模型預測調整（限縮幅度） |

利率範圍限制：2.5% ~ 12.0%（符合台灣中小企業市場實務）

---

## Step 4：Next.js Frontend

### 4.1 初始化專案

```bash
# 在 sme-loan-platform/ 資料夾執行
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*"

cd frontend/
```

### 4.2 安裝套件（此專案不需額外安裝，僅用 React 內建）

Next.js 14 + Tailwind CSS 已包含所有需要的功能。

### 4.3 替換主頁面

將提供的 `page.tsx` 複製到：

```bash
cp ../frontend-guide/page.tsx src/app/page.tsx
```

### 4.4 建立環境變數

```bash
# 在 frontend/ 資料夾建立 .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
```

> **重要**：`NEXT_PUBLIC_` 前綴讓 Next.js 把環境變數暴露給瀏覽器。

### 4.5 修改 layout.tsx（加入繁體中文字體）

```tsx
// src/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "永豐金控 AI法金貸款利率試算",
  description: "中小企業信貸風險評估與利率試算平台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-TW">
      <body style={{ margin: 0, fontFamily: "'Microsoft JhengHei', 'Noto Sans TC', sans-serif" }}>
        {children}
      </body>
    </html>
  );
}
```

### 4.6 啟動前端

```bash
npm run dev
```

打開 http://localhost:3000 即可看到完整 UI。

---

## Step 5：CORS 串接

### 為什麼要處理 CORS？
瀏覽器的安全機制：前端（port 3000）呼叫後端（port 8000）屬於跨域請求，後端必須明確允許。

### 後端已設定 CORS（main.py 第 29-38 行）：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 開發時
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 常見問題排除

**問題 1：瀏覽器顯示 CORS error**
```
Access to fetch at 'http://localhost:8000' from origin 'http://localhost:3000'
has been blocked by CORS policy
```
解法：確認 `main.py` 的 `allow_origins` 包含 `http://localhost:3000`，重啟 FastAPI。

**問題 2：422 Unprocessable Entity**
原因：送出的 JSON 欄位有問題（型別錯誤、缺少必填欄位）

診斷：看 FastAPI 回應的 `detail` 欄位：
```json
{
  "detail": [
    {"loc": ["body", "credit_score"], "msg": "value is not a valid integer", "type": "type_error.integer"}
  ]
}
```
解法：確認前端送出的型別與 Pydantic model 一致（數字不要用字串送）。

**問題 3：500 Internal Server Error**
看後端終端機的 error traceback，最常見是：
- 模型特徵名稱不符（`FEATURE_NAMES` 不對）
- 除以零（加 `max(..., 1)` 保護）

**用 curl 測試（繞過瀏覽器）**：
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "annual_revenue_ntd": 5000000,
    "years_in_business": 5,
    "num_employees": 20,
    "business_sector": "manufacturing",
    "credit_score": 680,
    "loan_amount_ntd": 2000000,
    "tenor_months": 36,
    "collateral_value_ntd": 2500000,
    "is_existing_customer": false,
    "has_credit_guarantee": false
  }'
```

---

## Step 6：部署

### 架構

```
GitHub Repo
  ├── backend/  → Render（免費方案）
  └── frontend/ → Vercel（免費方案）
```

### 6.1 後端部署到 Render

**準備 Procfile**（在 backend/ 資料夾建立）：

```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

**準備步驟**：

1. 在 GitHub 建立 repo，把整個 `sme-loan-platform/` 推上去
2. 到 https://render.com 註冊（免費）
3. 點 **New → Web Service**
4. 連接 GitHub repo
5. 設定：
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt && python train_model.py`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

6. 環境變數（Render → Environment）：
   ```
   ALLOWED_ORIGINS = https://your-frontend.vercel.app
   MODEL_PATH = model.pkl
   ```

7. 部署完成後，Render 給你一個網址，例如：
   `https://sme-loan-api.onrender.com`

> **注意**：Render 免費方案在無流量時會休眠，第一次請求需等 30-60 秒。

### 6.2 前端部署到 Vercel

1. 到 https://vercel.com 註冊
2. 點 **New Project**，選你的 GitHub repo
3. 設定：
   - **Root Directory**: `frontend`
   - **Framework Preset**: Next.js（自動偵測）
4. 環境變數（Vercel → Settings → Environment Variables）：
   ```
   NEXT_PUBLIC_API_URL = https://sme-loan-api.onrender.com
   ```
5. 點 **Deploy**

### 6.3 更新後端 CORS

回到 Render，在環境變數加入：
```
ALLOWED_ORIGINS = https://your-app.vercel.app
```

重新部署後端。

### 部署注意事項

- `model.pkl` 在 `build command` 執行 `train_model.py` 時產生
- CSV 資料集必須在 `backend/` 資料夾內（推上 GitHub）
- CSV 如果太大（>50MB），考慮用 Git LFS 或從外部 URL 下載

---

## Step 7：Demo 展示

### 啟動順序（本地開發）

```bash
# 終端機 1：後端
cd sme-loan-platform/backend
source venv/bin/activate
uvicorn main:app --reload --port 8000

# 終端機 2：前端
cd sme-loan-platform/frontend
npm run dev
```

瀏覽器開啟 http://localhost:3000

### Demo 展示流程（競賽用）

**情境 A：優質企業申請**
- 年營收：8,000,000
- 信用分數：750
- 產業：製造業
- 貸款：2,000,000 / 36個月
- 擔保品：3,000,000
- 預期結果：利率約 3.5-4.5%，等級1-2（優良/良好）

**情境 B：中等風險企業**
- 年營收：3,000,000
- 信用分數：620
- 產業：零售業
- 貸款：2,500,000 / 60個月
- 擔保品：2,000,000
- 預期結果：利率約 6-8%，等級4-5（普通/注意）

**情境 C：未通過規則閘門**
- 年營收：500,000（低於門檻 100萬）
- 信用分數：380（低於門檻 400）
- 預期結果：顯示規則閘門拒絕畫面

### Demo 要講的重點

1. **三層架構**：規則閘門 → ML模型（Stacking） → 市場利率調整
2. **台灣化**：使用台灣央行重貼現率、分行/區域主管審批體系
3. **可解釋性**：利率成分明細讓客戶理解每個加減項目
4. **商業價值**：信保基金折扣、客戶關係折扣體現銀行策略

---

## 常見錯誤排除

| 錯誤 | 原因 | 解法 |
|------|------|------|
| `ModuleNotFoundError: xgboost` | 套件未安裝 | `pip install -r requirements.txt` |
| `422 Unprocessable Entity` | 輸入格式錯誤 | 確認 JSON 欄位型別 |
| `CORS blocked` | 後端 CORS 設定不含前端網址 | 更新 `ALLOWED_ORIGINS` |
| `model.pkl not found` | 未執行 train_model.py | `python train_model.py` |
| Render 連線 timeout | 免費方案休眠 | 等30秒後刷新，或升級付費方案 |
| Next.js hydration error | 服務端/客戶端渲染不一致 | 加上 `"use client"` 指令 |
| `SMOTE` 錯誤 | 違約樣本太少 | 調整 `k_neighbors` 參數 |

---

## 快速啟動 Checklist

- [ ] Python 3.10+ 已安裝
- [ ] Node.js 18+ 已安裝
- [ ] `cd backend && pip install -r requirements.txt`
- [ ] 把 CSV 放到 `backend/` 資料夾
- [ ] `python train_model.py`（產生 model.pkl）
- [ ] `uvicorn main:app --reload`（後端啟動）
- [ ] `cd frontend && npm install && npm run dev`（前端啟動）
- [ ] 瀏覽器開啟 http://localhost:3000
- [ ] 測試 Demo 情境 A、B、C

---

*永豐金控 AI法金貸款利率試算平台 | 版本 1.0 | 2025*
