"""
永豐金控 AI法金貸款利率試算平台 - FastAPI Backend
版本：1.0 | Production-Ready
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional
import pickle
import os
import logging
import numpy as np
import pandas as pd
from pathlib import Path

# ─────────────────────────────────────────────
# 日誌設定
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# FastAPI App 初始化
# ─────────────────────────────────────────────
app = FastAPI(
    title="永豐金控 SME貸款利率試算API",
    description="AI驅動的中小企業法金貸款利率預測系統",
    version="1.0.0",
    docs_url="/docs",       # Swagger UI 路徑
    redoc_url="/redoc",     # ReDoc UI 路徑
)

# ─────────────────────────────────────────────
# CORS 設定（允許 Next.js 前端連線）
# 開發時允許 localhost:3000；部署後改為正式網址
# ─────────────────────────────────────────────
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# 全域 ML 模型（啟動時載入，避免每次請求重新載入）
# ─────────────────────────────────────────────
MODEL = None
SCALER = None
FEATURE_NAMES = None

def load_model():
    """啟動時載入 model.pkl"""
    global MODEL, SCALER, FEATURE_NAMES
    model_path = Path(os.getenv("MODEL_PATH", "model.pkl"))
    
    if not model_path.exists():
        logger.warning(f"⚠️  找不到 {model_path}，將使用規則式定價（無ML調整）")
        return False
    
    try:
        with open(model_path, "rb") as f:
            bundle = pickle.load(f)
        MODEL = bundle.get("model")
        SCALER = bundle.get("scaler")
        FEATURE_NAMES = bundle.get("feature_names")
        logger.info(f"✅ 模型載入成功，特徵數：{len(FEATURE_NAMES) if FEATURE_NAMES else 'N/A'}")
        return True
    except Exception as e:
        logger.error(f"❌ 模型載入失敗：{e}")
        return False


@app.on_event("startup")
async def startup_event():
    load_model()


# ═══════════════════════════════════════════════════════════════
# SECTION 1 — Request / Response Schema（Pydantic 資料驗證）
# ═══════════════════════════════════════════════════════════════

class LoanApplication(BaseModel):
    """
    貸款申請表單資料結構
    所有欄位都有型別驗證、預設值、說明
    """
    # 企業基本資料
    annual_revenue_ntd: float = Field(..., gt=0, description="年營收（新台幣）", example=5_000_000)
    years_in_business: int = Field(..., ge=1, le=100, description="營業年數", example=5)
    num_employees: int = Field(..., ge=1, le=10000, description="員工數", example=20)
    business_sector: str = Field(..., description="產業別", example="manufacturing")
    
    # 負責人資料
    credit_score: int = Field(..., ge=300, le=850, description="信用分數（300-850）", example=680)
    
    # 貸款條件
    loan_amount_ntd: float = Field(..., gt=0, le=50_000_000, description="貸款金額（新台幣）", example=2_000_000)
    tenor_months: int = Field(..., ge=6, le=84, description="貸款期限（月）", example=36)
    collateral_value_ntd: float = Field(..., ge=0, description="擔保品價值（新台幣）", example=2_500_000)
    
    # 選填項目
    is_existing_customer: bool = Field(False, description="是否為既有客戶")
    has_credit_guarantee: bool = Field(False, description="是否有信保基金擔保")

    @validator("business_sector")
    def validate_sector(cls, v):
        valid = {"manufacturing", "retail_trade", "services", "agriculture", "construction", "technology", "other"}
        if v not in valid:
            raise ValueError(f"產業別必須為：{', '.join(valid)}")
        return v


class RateComponent(BaseModel):
    """利率成分明細"""
    name: str
    rate: float
    rate_pct: str


class PredictionResponse(BaseModel):
    """API回傳結果"""
    # 核心結果
    final_rate: float
    final_rate_pct: str
    
    # 風險評估
    pd_score: float
    pd_score_pct: str
    risk_grade: int
    risk_grade_name: str
    risk_color: str
    
    # 利率成分
    components: list
    
    # 還款試算
    monthly_payment: float
    total_payment: float
    total_interest: float
    
    # 審批建議
    approval_decision: str
    approval_authority: str
    approval_conditions: str
    
    # 市場比較
    market_benchmark_rate: float
    rate_vs_market: float
    
    # 規則檢查
    is_eligible: bool
    failed_rules: list
    
    # 元資料
    ml_model_used: bool
    message: str


# ═══════════════════════════════════════════════════════════════
# SECTION 2 — 台灣市場基準利率（2025年實務）
# ═══════════════════════════════════════════════════════════════

# 台灣央行重貼現率（2025年2月）：1.875%
TAIWAN_REDISCOUNT_RATE = 0.01875

# 台灣5年期定存利率基準（商業銀行平均）：約2.0%
TAIWAN_5Y_DEPOSIT_RATE = 0.020

# 金融業隔夜拆款利率（TAIBOR Overnight，約1.85%）
TAIBOR_OVERNIGHT = 0.0185


class TaiwanMarketBenchmark:
    """
    台灣市場利率基準層
    
    設計原理：
    - 銀行放款成本 = 資金成本（央行重貼現率 + 存款利差）
    - 中小企業貸款加成 = 依風險等級動態調整
    - 所有參數皆可透過環境變數覆寫（彈性部署）
    """
    
    def __init__(self):
        # 基礎利率：讀取環境變數，預設為央行重貼現率 + 0.125%（銀行資金成本溢酬）
        self.base_rate = float(os.getenv("BASE_RATE", TAIWAN_REDISCOUNT_RATE + 0.00125))
        
        # 依信用評分分層風險溢酬（Credit Score Tier Premium）
        # 設計邏輯：信用分數越低，風險溢酬越高
        self.credit_score_tiers = [
            {"min": 750, "max": 850, "premium": 0.000, "label": "優質"},   # 優質客戶
            {"min": 700, "max": 749, "premium": 0.005, "label": "良好"},   # +0.5%
            {"min": 650, "max": 699, "premium": 0.015, "label": "尚可"},   # +1.5%
            {"min": 600, "max": 649, "premium": 0.030, "label": "普通"},   # +3.0%
            {"min": 550, "max": 599, "premium": 0.050, "label": "偏低"},   # +5.0%
            {"min": 300, "max": 549, "premium": 0.080, "label": "低"},     # +8.0%
        ]
        
        # 依負債比增加額外風險加成（DBR Surcharge）
        # 設計邏輯：負債營收比越高，還款壓力越大
        self.dbr_surcharge_tiers = [
            {"max_dbr": 0.5,  "surcharge": 0.000},   # DBR ≤ 50%：無加成
            {"max_dbr": 1.0,  "surcharge": 0.005},   # DBR 50-100%：+0.5%
            {"max_dbr": 2.0,  "surcharge": 0.015},   # DBR 100-200%：+1.5%
            {"max_dbr": 3.0,  "surcharge": 0.030},   # DBR 200-300%：+3.0%
            {"max_dbr": 5.0,  "surcharge": 0.050},   # DBR 300-500%：+5.0%
        ]
    
    def get_credit_score_premium(self, credit_score: int) -> tuple:
        """依信用分數取得風險溢酬"""
        for tier in self.credit_score_tiers:
            if tier["min"] <= credit_score <= tier["max"]:
                return tier["premium"], tier["label"]
        return 0.080, "低"   # fallback
    
    def get_dbr_surcharge(self, dbr: float) -> float:
        """依負債比取得額外加成"""
        for tier in self.dbr_surcharge_tiers:
            if dbr <= tier["max_dbr"]:
                return tier["surcharge"]
        return 0.050   # DBR超過上限


# ═══════════════════════════════════════════════════════════════
# SECTION 3 — Risk-Based Pricing Layer（風險定價核心）
# ═══════════════════════════════════════════════════════════════

class RiskBasedPricingLayer:
    """
    台灣法金貸款風險定價引擎
    
    最終利率公式：
        利率 = 市場基準 + 信用風險溢酬 + 負債比加成 + ML預測調整 + 其他調整
    
    設計依據：
    - 巴塞爾協定III資本適足率
    - 台灣銀行公會中小企業授信準則
    - 永豐銀行內部定價實務
    """
    
    def __init__(self):
        self.market = TaiwanMarketBenchmark()
        
        # 產業風險溢酬（依台灣各產業景氣風險）
        self.industry_premium = {
            "manufacturing":  0.0000,   # 製造業：台灣核心優勢，基準
            "technology":     0.0000,   # 科技業：台灣護城河，基準
            "services":       0.0025,   # 服務業：+0.25%
            "retail_trade":   0.0030,   # 零售業：+0.30%
            "construction":   0.0040,   # 營建業：+0.40%（專案風險）
            "agriculture":    0.0045,   # 農業：+0.45%（天候風險）
            "other":          0.0030,   # 其他：+0.30%
        }
        
        # 期限溢酬（每年0.15%，補償長期不確定性）
        self.maturity_premium_per_year = 0.0015
        
        # 規模折扣（大額貸款享有規模經濟）
        self.size_discount_per_10m = 0.0008  # 每1000萬折扣0.08%
        self.max_size_discount = 0.0100       # 最大折扣1%
        
        # 市場競爭調整（銀行間競爭激烈）
        self.competitive_discount = -0.0050
        
        # 客戶關係折扣
        self.relationship_discount = -0.0030
        
        # 信保基金折扣
        self.credit_guarantee_discount = -0.0025
        
        # 利率上下限（符合台灣中小企業貸款實務）
        self.min_rate = 0.025    # 2.5%（防止低於成本）
        self.max_rate = 0.120    # 12%（法規上限）
    
    def calculate(
        self,
        pd_score: float,
        credit_score: int,
        dbr: float,
        loan_amount_ntd: float,
        tenor_months: int,
        industry: str,
        collateral_coverage: float,
        is_existing_customer: bool,
        has_credit_guarantee: bool,
        ml_adjustment: float = 0.0
    ) -> dict:
        """
        計算最終利率（含所有成分）
        
        參數說明：
            pd_score         - ML模型預測的違約機率（0~1）
            credit_score     - 申請人信用分數
            dbr              - 負債營收比
            loan_amount_ntd  - 貸款金額（台幣）
            tenor_months     - 貸款期限（月）
            industry         - 產業別
            collateral_coverage - 擔保覆蓋率
            is_existing_customer - 既有客戶
            has_credit_guarantee - 有信保基金
            ml_adjustment    - ML模型微調值（通常 ±0.5% 以內）
        """
        # ── 1. 市場基準利率（台灣央行重貼現率 + 銀行資金溢酬）
        base = self.market.base_rate
        
        # ── 2. 信用評分風險溢酬
        credit_premium, credit_label = self.market.get_credit_score_premium(credit_score)
        
        # ── 3. 負債比額外加成
        dbr_surcharge = self.market.get_dbr_surcharge(dbr)
        
        # ── 4. 預期損失成本（PD × LGD，LGD隨擔保品調整）
        lgd = 0.40 * (1 - min(collateral_coverage * 0.4, 0.4))
        expected_loss = pd_score * lgd
        
        # ── 5. 資金成本（銀行存款成本 + 管理成本）
        funding_cost = 0.0100  # 1.00%
        
        # ── 6. 目標利差（銀行獲利目標）
        target_spread = 0.0150  # 1.50%
        
        # ── 7. 期限溢酬
        maturity_premium = self.maturity_premium_per_year * (tenor_months / 12)
        
        # ── 8. 規模折扣（大額貸款）
        size_discount = max(
            -self.size_discount_per_10m * (loan_amount_ntd / 10_000_000),
            -self.max_size_discount
        )
        
        # ── 9. 產業溢酬
        industry_prem = self.industry_premium.get(industry, 0.0030)
        
        # ── 10. 市場競爭調整
        competitive_adj = self.competitive_discount
        
        # ── 11. 客戶關係折扣
        relationship_adj = self.relationship_discount if is_existing_customer else 0.0
        
        # ── 12. 信保基金折扣
        guarantee_adj = self.credit_guarantee_discount if has_credit_guarantee else 0.0
        
        # ── 13. ML模型微調（限制幅度避免過度影響）
        ml_adj = max(-0.005, min(ml_adjustment, 0.005))
        
        # ── 14. 合計最終利率
        total = (
            base + credit_premium + dbr_surcharge +
            expected_loss + funding_cost + target_spread +
            maturity_premium + size_discount + industry_prem +
            competitive_adj + relationship_adj + guarantee_adj + ml_adj
        )
        
        # ── 15. 限制在合法範圍
        final_rate = max(self.min_rate, min(total, self.max_rate))
        
        return {
            "final_rate": final_rate,
            "components": {
                "市場基準利率": base,
                "信用評分溢酬": credit_premium,
                "負債比加成": dbr_surcharge,
                "預期損失成本(PD×LGD)": expected_loss,
                "資金成本": funding_cost,
                "目標利差": target_spread,
                "期限溢酬": maturity_premium,
                "規模折扣": size_discount,
                "產業溢酬": industry_prem,
                "市場競爭調整": competitive_adj,
                "客戶關係折扣": relationship_adj,
                "信保擔保折扣": guarantee_adj,
                "ML模型微調": ml_adj,
            },
            "credit_label": credit_label,
            "raw_total_before_cap": total,
        }


# ═══════════════════════════════════════════════════════════════
# SECTION 4 — 輔助系統（規則閘門、風險分級、市場基準）
# ═══════════════════════════════════════════════════════════════

RISK_GRADES = {
    1: {"name": "優良", "pd_max": 0.005, "color": "#28a745", "market_rate": 0.0280},
    2: {"name": "良好", "pd_max": 0.010, "color": "#5cb85c", "market_rate": 0.0350},
    3: {"name": "尚可", "pd_max": 0.025, "color": "#f0ad4e", "market_rate": 0.0450},
    4: {"name": "普通", "pd_max": 0.050, "color": "#ec971f", "market_rate": 0.0580},
    5: {"name": "注意", "pd_max": 0.100, "color": "#d58512", "market_rate": 0.0720},
    6: {"name": "次級", "pd_max": 0.200, "color": "#d9534f", "market_rate": 0.0900},
    7: {"name": "可疑", "pd_max": 0.500, "color": "#c9302c", "market_rate": 0.1100},
    8: {"name": "損失", "pd_max": 1.000, "color": "#ac2925", "market_rate": 0.1200},
}

APPROVAL_MATRIX = {
    1: {"decision": "建議核准", "authority": "分行經理",  "conditions": "標準條件"},
    2: {"decision": "建議核准", "authority": "分行經理",  "conditions": "標準條件"},
    3: {"decision": "建議核准", "authority": "區域主管",  "conditions": "標準條件加強擔保"},
    4: {"decision": "條件核准", "authority": "區域主管",  "conditions": "需額外擔保或保證人"},
    5: {"decision": "條件核准", "authority": "總行審查",  "conditions": "強化擔保及密切追蹤"},
    6: {"decision": "審慎評估", "authority": "總行審查",  "conditions": "特別簽報及風險控管"},
    7: {"decision": "不建議核准","authority": "總行審查",  "conditions": "除非有特殊理由及高階核准"},
    8: {"decision": "拒絕",     "authority": "N/A",       "conditions": "不符合授信政策"},
}


def classify_risk_grade(pd_score: float) -> int:
    for grade, info in RISK_GRADES.items():
        if pd_score < info["pd_max"]:
            return grade
    return 8


def check_rule_gate(app_data: dict) -> tuple:
    """
    硬性規則檢查（在ML推論前執行）
    返回：(is_eligible, failed_rules)
    """
    rules = [
        ("最低年營收 NT$1,000,000",
         app_data["annual_revenue_ntd"] >= 1_000_000,
         f"NT$ {app_data['annual_revenue_ntd']:,.0f}",
         "NT$ 1,000,000"),
        ("最低信用分數 400",
         app_data["credit_score"] >= 400,
         str(app_data["credit_score"]),
         "400"),
        ("最低營業年數 1年",
         app_data["years_in_business"] >= 1,
         f"{app_data['years_in_business']} 年",
         "1 年"),
        ("DBR不得超過500%",
         app_data["dbr"] <= 5.0,
         f"{app_data['dbr']*100:.1f}%",
         "500%"),
        ("擔保覆蓋率不得低於50%",
         app_data["collateral_coverage"] >= 0.5,
         f"{app_data['collateral_coverage']*100:.1f}%",
         "50%"),
    ]
    failed = []
    for name, passed, actual, required in rules:
        if not passed:
            failed.append({"rule": name, "actual": actual, "required": required})
    return len(failed) == 0, failed


def calculate_monthly_payment(loan_amount: float, annual_rate: float, tenor_months: int) -> float:
    """本息平均攤還法計算月付金額"""
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        return loan_amount / tenor_months
    return loan_amount * monthly_rate * (1 + monthly_rate)**tenor_months / ((1 + monthly_rate)**tenor_months - 1)


# ═══════════════════════════════════════════════════════════════
# SECTION 5 — ML 推論函數
# ═══════════════════════════════════════════════════════════════

def predict_pd_from_model(features: dict) -> tuple:
    """
    使用 ML 模型預測違約機率
    回傳：(pd_score, ml_adjustment, used_model)
    """
    global MODEL, SCALER, FEATURE_NAMES
    
    if MODEL is None or SCALER is None or FEATURE_NAMES is None:
        # 無模型時，使用信用分數簡單估算PD
        cs = features.get("credit_score", 600)
        pd_score = max(0.001, min(0.5, (800 - cs) / 800 * 0.15))
        return pd_score, 0.0, False
    
    try:
        # 建立特徵向量（依訓練時的特徵順序）
        row = {name: features.get(name, 0.0) for name in FEATURE_NAMES}
        X = pd.DataFrame([row])[FEATURE_NAMES].fillna(0)
        X_scaled = SCALER.transform(X)
        
        # 預測 PD
        pd_raw = float(MODEL.predict_proba(X_scaled)[:, 1][0])
        
        # 宏觀校準（尼日利亞訓練集違約率≈16%，台灣實際≈2%）
        calibration_factor = 0.02 / 0.16
        pd_calibrated = max(0.0001, min(pd_raw * calibration_factor, 0.9999))
        
        # ML微調值：模型PD相對簡單估算的差距（縮放至 ±0.5%）
        simple_pd = max(0.001, min(0.5, (800 - features.get("credit_score", 600)) / 800 * 0.15))
        ml_adjustment = (pd_calibrated - simple_pd) * 0.1  # 縮小影響幅度
        
        return pd_calibrated, ml_adjustment, True
    except Exception as e:
        logger.error(f"ML推論失敗：{e}")
        cs = features.get("credit_score", 600)
        pd_score = max(0.001, min(0.5, (800 - cs) / 800 * 0.15))
        return pd_score, 0.0, False


# ═══════════════════════════════════════════════════════════════
# SECTION 6 — API 路由
# ═══════════════════════════════════════════════════════════════

@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "永豐金控 SME利率試算API", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "model_loaded": MODEL is not None,
        "taiwan_base_rate": f"{TAIWAN_REDISCOUNT_RATE*100:.3f}%",
    }


@app.post("/predict", response_model=PredictionResponse, tags=["Prediction"])
async def predict_interest_rate(application: LoanApplication):
    """
    主要預測端點：輸入企業資料，回傳風險評估 + 建議貸款利率
    
    流程：
    1. 資料驗證（Pydantic 自動執行）
    2. 規則閘門檢查（硬性准入條件）
    3. ML模型預測違約機率（PD）
    4. Risk-Based Pricing 計算最終利率
    5. 回傳完整評估結果
    """
    
    # ── 衍生指標計算
    dbr = application.loan_amount_ntd / max(application.annual_revenue_ntd, 1)
    collateral_coverage = application.collateral_value_ntd / max(application.loan_amount_ntd, 1)
    
    # ── 規則閘門檢查
    app_data = {
        "annual_revenue_ntd": application.annual_revenue_ntd,
        "credit_score": application.credit_score,
        "years_in_business": application.years_in_business,
        "dbr": dbr,
        "collateral_coverage": collateral_coverage,
    }
    is_eligible, failed_rules = check_rule_gate(app_data)
    
    if not is_eligible:
        # 仍回傳結果（含失敗原因），由前端決定如何呈現
        return PredictionResponse(
            final_rate=0.0,
            final_rate_pct="N/A",
            pd_score=0.0,
            pd_score_pct="N/A",
            risk_grade=8,
            risk_grade_name="損失",
            risk_color="#ac2925",
            components=[],
            monthly_payment=0.0,
            total_payment=0.0,
            total_interest=0.0,
            approval_decision="拒絕",
            approval_authority="N/A",
            approval_conditions="未通過基本准入條件",
            market_benchmark_rate=0.0,
            rate_vs_market=0.0,
            is_eligible=False,
            failed_rules=failed_rules,
            ml_model_used=False,
            message="申請案未通過基本准入規則檢查，請修正後再申請",
        )
    
    # ── ML 預測 PD
    ml_features = {
        "annual_revenue_ntd": application.annual_revenue_ntd,
        "revenue_per_employee": application.annual_revenue_ntd / max(application.num_employees, 1),
        "years_in_business": application.years_in_business,
        "num_employees": application.num_employees,
        "business_growth_proxy": dbr,
        "credit_score": application.credit_score,
        "owner_experience_years": application.years_in_business,
        "business_sector_risk": {"manufacturing":0.15,"retail_trade":0.20,"services":0.25,
                                  "agriculture":0.30,"construction":0.28,"technology":0.22,"other":0.25
                                  }.get(application.business_sector, 0.25),
        "loan_amount_ntd": application.loan_amount_ntd,
        "debt_to_revenue_ratio": dbr,
        "collateral_coverage": collateral_coverage,
        "tenor_months": application.tenor_months,
        "existing_debt_proxy": 0.08,
    }
    
    pd_score, ml_adjustment, ml_used = predict_pd_from_model(ml_features)
    
    # ── Risk-Based Pricing
    pricer = RiskBasedPricingLayer()
    pricing = pricer.calculate(
        pd_score=pd_score,
        credit_score=application.credit_score,
        dbr=dbr,
        loan_amount_ntd=application.loan_amount_ntd,
        tenor_months=application.tenor_months,
        industry=application.business_sector,
        collateral_coverage=collateral_coverage,
        is_existing_customer=application.is_existing_customer,
        has_credit_guarantee=application.has_credit_guarantee,
        ml_adjustment=ml_adjustment,
    )
    
    final_rate = pricing["final_rate"]
    
    # ── 風險等級分類
    risk_grade = classify_risk_grade(pd_score)
    grade_info = RISK_GRADES[risk_grade]
    approval = APPROVAL_MATRIX[risk_grade]
    
    # ── 還款試算
    monthly_payment = calculate_monthly_payment(
        application.loan_amount_ntd, final_rate, application.tenor_months
    )
    total_payment = monthly_payment * application.tenor_months
    total_interest = total_payment - application.loan_amount_ntd
    
    # ── 市場比較
    market_rate = grade_info["market_rate"]
    
    # ── 整理成分明細
    components_list = [
        {"name": k, "rate": v, "rate_pct": f"{v*100:+.2f}%"}
        for k, v in pricing["components"].items()
    ]
    
    return PredictionResponse(
        final_rate=round(final_rate, 6),
        final_rate_pct=f"{final_rate*100:.2f}%",
        pd_score=round(pd_score, 6),
        pd_score_pct=f"{pd_score*100:.2f}%",
        risk_grade=risk_grade,
        risk_grade_name=grade_info["name"],
        risk_color=grade_info["color"],
        components=components_list,
        monthly_payment=round(monthly_payment, 0),
        total_payment=round(total_payment, 0),
        total_interest=round(total_interest, 0),
        approval_decision=approval["decision"],
        approval_authority=approval["authority"],
        approval_conditions=approval["conditions"],
        market_benchmark_rate=market_rate,
        rate_vs_market=round(final_rate - market_rate, 6),
        is_eligible=True,
        failed_rules=[],
        ml_model_used=ml_used,
        message="評估完成",
    )
